import { createHash } from "node:crypto";
import { ConditionalCheckFailedException, DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { deviceKey, type LimitDeps, take } from "../src/limits";

const AT_10_59 = Date.parse("2026-10-30T10:59:00Z") / 1000;
const AT_11_00 = Date.parse("2026-10-30T11:00:00Z") / 1000;
const DEVICE = "device-0123456789abcdef";

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ddbMock = mockClient(ddb);

function deps(): LimitDeps {
  return { ddb, limitsTableName: "limits" };
}

function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

// The mock never evaluates a ConditionExpression, so this fake does what DynamoDB would with
// the one condition take sends, and its exact text is checked below (T5).
let counts: Map<string, number>;
function fakeCounters(): void {
  counts = new Map();
  ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
    const pk = input.Key?.pk as string;
    const values = input.ExpressionAttributeValues ?? {};
    const n = counts.get(pk);
    if (input.ConditionExpression !== undefined && n !== undefined && n >= values[":limit"]) {
      throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
    }
    counts.set(pk, (n ?? 0) + (values[":one"] ?? values[":minusOne"]));
    return {};
  });
}

function updates(): UpdateCommandInput[] {
  return ddbMock.commandCalls(UpdateCommand).map((call) => call.args[0].input);
}

beforeEach(() => {
  ddbMock.reset();
  fakeCounters();
});

describe("take", () => {
  it("takes the 10th upload of a clock hour and refuses the 11th with device_limit and a Retry-After", async () => {
    for (let i = 0; i < 10; i++) expect(await take("upload", DEVICE, AT_10_59, deps())).toBeNull();

    const res = await take("upload", DEVICE, AT_10_59, deps());

    expect(res?.statusCode).toBe(429);
    expect(JSON.parse(res?.body ?? "")).toEqual({ error: "device_limit" });
    expect(res?.headers["content-type"]).toBe("application/json");
    expect(res?.headers["retry-after"]).toBe("60");
    expect(counts.get(`upload#${sha256(DEVICE)}#2026-10-30T10`)).toBe(10);
  });

  it("starts again in the next UTC hour", async () => {
    for (let i = 0; i < 10; i++) await take("upload", DEVICE, AT_10_59, deps());
    expect((await take("upload", DEVICE, AT_10_59, deps()))?.statusCode).toBe(429);

    expect(await take("upload", DEVICE, AT_11_00, deps())).toBeNull();
    expect(counts.get(`upload#${sha256(DEVICE)}#2026-10-30T11`)).toBe(1);
  });

  it("counts a missing, short, overlong or malformed id in the shared none bucket", async () => {
    const bad = [undefined, "", "abc1234", "a".repeat(65), "has space 123", "semi;colon12", "ünïcödé-123"];
    for (const header of bad) expect(deviceKey(header)).toBe("none");
    // Both edges of the length range are well formed.
    expect(deviceKey("a".repeat(8))).toBe("a".repeat(8));
    expect(deviceKey("A_b-".repeat(16))).toBe("A_b-".repeat(16));

    for (const header of bad) await take("upload", header, AT_10_59, deps());

    const none = `upload#${sha256("none")}#2026-10-30T10`;
    expect(counts.get(none)).toBe(7);
    expect(updates().filter((input) => input.Key?.pk !== "upload#ALL#2026-10-30T10").every((input) => input.Key?.pk === none)).toBe(true);
  });

  it("refuses the 301st upload of the hour in all with global_cap, and gives the device's count back", async () => {
    // 30 devices at their limit of 10 make the hour's 300.
    for (let d = 0; d < 30; d++) {
      for (let i = 0; i < 10; i++) expect(await take("upload", `device-${d}-padding`, AT_10_59, deps())).toBeNull();
    }

    const res = await take("upload", DEVICE, AT_10_59, deps());

    expect(res?.statusCode).toBe(429);
    expect(JSON.parse(res?.body ?? "")).toEqual({ error: "global_cap" });
    expect(res?.headers["retry-after"]).toBe("60");
    expect(counts.get("upload#ALL#2026-10-30T10")).toBe(300);
    expect(counts.get(`upload#${sha256(DEVICE)}#2026-10-30T10`)).toBe(0);
  });

  it("caps sample runs at 5 per device and 30 in all", async () => {
    for (let i = 0; i < 5; i++) expect(await take("sample", DEVICE, AT_10_59, deps())).toBeNull();
    const sixth = await take("sample", DEVICE, AT_10_59, deps());
    expect(sixth?.statusCode).toBe(429);
    expect(JSON.parse(sixth?.body ?? "")).toEqual({ error: "device_limit" });

    // Five more devices at 5 each bring the hour's sample runs to 30.
    for (let d = 0; d < 5; d++) {
      for (let i = 0; i < 5; i++) expect(await take("sample", `device-${d}-padding`, AT_10_59, deps())).toBeNull();
    }
    const thirtyFirst = await take("sample", "device-another-one", AT_10_59, deps());
    expect(thirtyFirst?.statusCode).toBe(429);
    expect(JSON.parse(thirtyFirst?.body ?? "")).toEqual({ error: "global_cap" });
    expect(counts.get("sample#ALL#2026-10-30T10")).toBe(30);

    // Uploads keep their own counters.
    expect(await take("upload", DEVICE, AT_10_59, deps())).toBeNull();
  });

  it("sends its exact update and condition, with :limit 10 and 300 for uploads and 5 and 30 for samples", async () => {
    const expiresAt = Date.parse("2026-10-30T10:00:00Z") / 1000 + 7200;
    const increment = (pk: string, limit: number) => ({
      TableName: "limits",
      Key: { pk },
      UpdateExpression: "ADD #n :one SET #expiresAt = :expiresAt",
      ConditionExpression: "attribute_not_exists(#n) OR #n < :limit",
      ExpressionAttributeNames: { "#n": "n", "#expiresAt": "expiresAt" },
      ExpressionAttributeValues: { ":one": 1, ":limit": limit, ":expiresAt": expiresAt },
    });
    const device = (bucket: string) => `${bucket}#${sha256(DEVICE)}#2026-10-30T10`;

    await take("upload", DEVICE, AT_10_59, deps());
    await take("sample", DEVICE, AT_10_59, deps());
    expect(updates()).toEqual([
      increment(device("upload"), 10),
      increment("upload#ALL#2026-10-30T10", 300),
      increment(device("sample"), 5),
      increment("sample#ALL#2026-10-30T10", 30),
    ]);

    // The give-back, when the hour's cap refuses.
    ddbMock.reset();
    fakeCounters();
    counts.set("upload#ALL#2026-10-30T10", 300);
    await take("upload", DEVICE, AT_10_59, deps());
    expect(updates()).toEqual([
      increment(device("upload"), 10),
      increment("upload#ALL#2026-10-30T10", 300),
      {
        TableName: "limits",
        Key: { pk: device("upload") },
        UpdateExpression: "ADD #n :minusOne",
        ExpressionAttributeNames: { "#n": "n" },
        ExpressionAttributeValues: { ":minusOne": -1 },
      },
    ]);
  });

  it("stores only the id's SHA-256, under {bucket}#{hash}#{YYYY-MM-DDTHH}, with a 2-hour TTL", async () => {
    await take("upload", DEVICE, AT_10_59, deps());

    const [first, second] = updates();
    expect(first.Key).toEqual({ pk: `upload#${sha256(DEVICE)}#2026-10-30T10` });
    expect(second.Key).toEqual({ pk: "upload#ALL#2026-10-30T10" });
    for (const input of updates()) {
      expect(JSON.stringify(input)).not.toContain(DEVICE);
      expect(input.ExpressionAttributeValues?.[":expiresAt"]).toBe(Date.parse("2026-10-30T10:00:00Z") / 1000 + 7200);
    }
  });

  it("sets Retry-After to the seconds left in the UTC hour", async () => {
    ddbMock.reset();
    ddbMock.on(UpdateCommand).rejects(new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} }));

    const atTheMinute = await take("upload", DEVICE, AT_10_59, deps());
    const onTheHour = await take("upload", DEVICE, AT_11_00, deps());

    expect(atTheMinute?.headers["retry-after"]).toBe("60");
    expect(onTheHour?.headers["retry-after"]).toBe("3600");
  });

  it("lets any other DynamoDB error through", async () => {
    ddbMock.reset();
    ddbMock.on(UpdateCommand).rejects(Object.assign(new Error("throttled"), { name: "ProvisionedThroughputExceededException" }));

    await expect(take("upload", DEVICE, AT_10_59, deps())).rejects.toThrow("throttled");
  });
});
