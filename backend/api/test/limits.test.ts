import { createHash } from "node:crypto";
import { ConditionalCheckFailedException, DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { type Bucket, deviceKey, giveBack, LIMIT_CODES, LIMITS, type LimitDeps, retryAfterS, take } from "../src/limits";

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

  it("sends its exact update and condition, with :limit 10 and 300 for uploads and 5, 30 and the day's 150 for samples", async () => {
    const expiresAt = Date.parse("2026-10-30T10:00:00Z") / 1000 + 7200;
    const dayExpiresAt = Date.parse("2026-10-30T00:00:00Z") / 1000 + 2 * 86400;
    const increment = (pk: string, limit: number, at = expiresAt) => ({
      TableName: "limits",
      Key: { pk },
      UpdateExpression: "ADD #n :one SET #expiresAt = :expiresAt",
      ConditionExpression: "attribute_not_exists(#n) OR #n < :limit",
      ExpressionAttributeNames: { "#n": "n", "#expiresAt": "expiresAt" },
      ExpressionAttributeValues: { ":one": 1, ":limit": limit, ":expiresAt": at },
    });
    const device = (bucket: string) => `${bucket}#${sha256(DEVICE)}#2026-10-30T10`;

    await take("upload", DEVICE, AT_10_59, deps());
    await take("sample", DEVICE, AT_10_59, deps());
    expect(updates()).toEqual([
      increment(device("upload"), 10),
      increment("upload#ALL#2026-10-30T10", 300),
      increment(device("sample"), 5),
      increment("sample#ALL#2026-10-30T10", 30),
      increment("sample#ALL#2026-10-30", 150, dayExpiresAt),
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

// Ask Lusot's questions (Task 6): MS4's take, with codes of their own.
describe("take for questions", () => {
  const body = (res: Awaited<ReturnType<typeof take>>) => JSON.parse(res?.body ?? "");

  it("the 20th question in an hour passes, the 21st is refused with question_limit and a Retry-After, and the next hour passes", async () => {
    expect(LIMITS.question).toEqual({ device: 20, all: 60 });
    for (let i = 0; i < 20; i++) expect(await take("question", DEVICE, AT_10_59, deps())).toBeNull();

    const res = await take("question", DEVICE, AT_10_59, deps());

    expect(res?.statusCode).toBe(429);
    expect(body(res)).toEqual({ error: "question_limit" });
    expect(res?.headers["retry-after"]).toBe("60");
    expect(counts.get(`question#${sha256(DEVICE)}#2026-10-30T10`)).toBe(20);
    // The device refused it, so it never reached the hour's count.
    expect(counts.get("question#ALL#2026-10-30T10")).toBe(20);

    // The device's hash, then the hour in all, each with the 2-hour TTL.
    const expiresAt = Date.parse("2026-10-30T10:00:00Z") / 1000 + 7200;
    const [device, all] = updates();
    expect([device.Key, device.ExpressionAttributeValues]).toEqual([
      { pk: `question#${sha256(DEVICE)}#2026-10-30T10` },
      { ":one": 1, ":limit": 20, ":expiresAt": expiresAt },
    ]);
    expect([all.Key, all.ExpressionAttributeValues]).toEqual([
      { pk: "question#ALL#2026-10-30T10" },
      { ":one": 1, ":limit": 60, ":expiresAt": expiresAt },
    ]);
    for (const input of updates()) expect(JSON.stringify(input)).not.toContain(DEVICE);

    expect(await take("question", DEVICE, AT_11_00, deps())).toBeNull();
    expect(counts.get(`question#${sha256(DEVICE)}#2026-10-30T11`)).toBe(1);
  });

  it("the 60th question in all passes, and the 61st is refused with question_cap and gives the device's count back", async () => {
    // 3 devices at their limit of 20 make the hour's 60; the last take of the loop is the 60th.
    for (let d = 0; d < 3; d++) {
      for (let i = 0; i < 20; i++) expect(await take("question", `device-${d}-padding`, AT_10_59, deps())).toBeNull();
    }
    expect(counts.get("question#ALL#2026-10-30T10")).toBe(60);

    const res = await take("question", DEVICE, AT_10_59, deps());

    expect(res?.statusCode).toBe(429);
    expect(body(res)).toEqual({ error: "question_cap" });
    expect(res?.headers["retry-after"]).toBe("60");
    expect(counts.get("question#ALL#2026-10-30T10")).toBe(60);
    expect(counts.get(`question#${sha256(DEVICE)}#2026-10-30T10`)).toBe(0);
    // Uploads keep their own counters.
    expect(await take("upload", DEVICE, AT_10_59, deps())).toBeNull();
  });

  it("uploads and samples keep device_limit and global_cap", async () => {
    expect(LIMIT_CODES).toEqual({
      upload: { device: "device_limit", all: "global_cap" },
      sample: { device: "device_limit", all: "global_cap" },
      try: { device: "device_limit", all: "global_cap" },
      question: { device: "question_limit", all: "question_cap" },
    });
    const expected: Record<Bucket, [string, string]> = {
      upload: ["device_limit", "global_cap"],
      sample: ["device_limit", "global_cap"],
      try: ["device_limit", "global_cap"],
      question: ["question_limit", "question_cap"],
    };
    for (const bucket of ["upload", "sample", "try", "question"] as const) {
      for (let i = 0; i < LIMITS[bucket].device; i++) await take(bucket, DEVICE, AT_10_59, deps());
      const byDevice = await take(bucket, DEVICE, AT_10_59, deps());
      counts.set(`${bucket}#ALL#2026-10-30T10`, LIMITS[bucket].all);
      const byHour = await take(bucket, "device-another-one", AT_10_59, deps());

      expect([byDevice?.statusCode, byHour?.statusCode], bucket).toEqual([429, 429]);
      expect([body(byDevice).error, body(byHour).error], bucket).toEqual(expected[bucket]);
    }
  });

  it("Retry-After is retryAfterS's: 3,600 at the top of an hour, 1 a second before the next", async () => {
    const AT_11_59_59 = Date.parse("2026-10-30T11:59:59Z") / 1000;
    for (const [nowS, seconds] of [
      [AT_11_00, "3600"],
      [AT_11_59_59, "1"],
    ] as const) {
      expect(String(retryAfterS(nowS))).toBe(seconds);
      counts.set(`question#${sha256(DEVICE)}#2026-10-30T11`, 20);
      counts.set("question#ALL#2026-10-30T11", 60);

      const byDevice = await take("question", DEVICE, nowS, deps());
      const byHour = await take("question", "device-another-one", nowS, deps());

      expect([body(byDevice).error, byDevice?.headers["retry-after"]]).toEqual(["question_limit", seconds]);
      expect([body(byHour).error, byHour?.headers["retry-after"]]).toEqual(["question_cap", seconds]);
    }
  });
});

// "Try your own photo" (C534): its own bucket, and a cap per UTC day for it and for samples, so judging
// can't drain the Meta credits.
describe("take for chosen photos and the day caps", () => {
  const body = (res: Awaited<ReturnType<typeof take>>) => JSON.parse(res?.body ?? "");
  const DAY_S = 86400;

  it("caps chosen photos at 3 per device and 20 an hour in all, and 120 a UTC day in all", () => {
    expect(LIMITS.try).toEqual({ device: 3, all: 20, day: 120 });
    expect(LIMITS.sample).toEqual({ device: 5, all: 30, day: 150 });
    // Uploads and questions have no day cap.
    expect(LIMITS.upload).toEqual({ device: 10, all: 300 });
    expect(LIMITS.question).toEqual({ device: 20, all: 60 });
  });

  it("refuses a device's 4th chosen photo of the hour with device_limit, before the hour or the day counts it", async () => {
    for (let i = 0; i < 3; i++) expect(await take("try", DEVICE, AT_10_59, deps())).toBeNull();

    const res = await take("try", DEVICE, AT_10_59, deps());

    expect(res?.statusCode).toBe(429);
    expect(body(res)).toEqual({ error: "device_limit" });
    expect(counts.get(`try#${sha256(DEVICE)}#2026-10-30T10`)).toBe(3);
    expect(counts.get("try#ALL#2026-10-30T10")).toBe(3);
    expect(counts.get("try#ALL#2026-10-30")).toBe(3);
  });

  it("refuses the 21st chosen photo of the hour in all with global_cap, and gives the device's count back", async () => {
    counts.set("try#ALL#2026-10-30T10", 20);

    const res = await take("try", DEVICE, AT_10_59, deps());

    expect(body(res)).toEqual({ error: "global_cap" });
    expect(counts.get(`try#${sha256(DEVICE)}#2026-10-30T10`)).toBe(0);
    expect(counts.get("try#ALL#2026-10-30")).toBeUndefined();
  });

  it("refuses the day's 121st chosen photo with daily_cap and a Retry-After to the next UTC midnight, and gives the hour's counts back", async () => {
    counts.set("try#ALL#2026-10-30", 120);

    const res = await take("try", DEVICE, AT_10_59, deps());

    expect(res?.statusCode).toBe(429);
    expect(body(res)).toEqual({ error: "daily_cap" });
    expect(res?.headers["retry-after"]).toBe(String(Date.parse("2026-10-31T00:00:00Z") / 1000 - AT_10_59));
    expect(counts.get("try#ALL#2026-10-30")).toBe(120);
    expect(counts.get(`try#${sha256(DEVICE)}#2026-10-30T10`)).toBe(0);
    expect(counts.get("try#ALL#2026-10-30T10")).toBe(0);
  });

  it("refuses the day's 151st sample run with daily_cap", async () => {
    counts.set("sample#ALL#2026-10-30", 150);

    const res = await take("sample", DEVICE, AT_10_59, deps());

    expect(body(res)).toEqual({ error: "daily_cap" });
    expect(counts.get(`sample#${sha256(DEVICE)}#2026-10-30T10`)).toBe(0);
    expect(counts.get("sample#ALL#2026-10-30T10")).toBe(0);
  });

  it("keys the day as {bucket}#ALL#{YYYY-MM-DD}, kept 2 days from its start, and starts again the next UTC day", async () => {
    const AT_23_59 = Date.parse("2026-10-30T23:59:59Z") / 1000;
    const NEXT_DAY = AT_23_59 + 1;
    counts.set("try#ALL#2026-10-30", 120);
    expect(body(await take("try", DEVICE, AT_23_59, deps()))).toEqual({ error: "daily_cap" });
    expect((await take("try", DEVICE, AT_23_59, deps()))?.headers["retry-after"]).toBe("1");

    expect(await take("try", DEVICE, NEXT_DAY, deps())).toBeNull();

    expect(counts.get("try#ALL#2026-10-31")).toBe(1);
    const day = updates().filter((input) => input.Key?.pk === "try#ALL#2026-10-31");
    expect(day).toHaveLength(1);
    expect(day[0].ExpressionAttributeValues).toEqual({ ":one": 1, ":limit": 120, ":expiresAt": NEXT_DAY + 2 * DAY_S });
  });

  it("never counts a day for uploads or questions", async () => {
    await take("upload", DEVICE, AT_10_59, deps());
    await take("question", DEVICE, AT_10_59, deps());

    expect(updates().map((input) => input.Key?.pk)).not.toContain("upload#ALL#2026-10-30");
    expect(updates()).toHaveLength(4);
  });
});

describe("giveBack", () => {
  it("takes one question off the device's hour and the hour in all, so a taken question nets to nothing", async () => {
    expect(await take("question", DEVICE, AT_10_59, deps())).toBeNull();
    expect(await take("question", DEVICE, AT_10_59, deps())).toBeNull();

    await giveBack("question", DEVICE, AT_10_59, deps());

    expect(counts.get(`question#${sha256(DEVICE)}#2026-10-30T10`)).toBe(1);
    expect(counts.get("question#ALL#2026-10-30T10")).toBe(1);
    const [device, all] = updates().slice(-2);
    for (const input of [device, all]) {
      expect(input).toMatchObject({
        TableName: "limits",
        UpdateExpression: "ADD #n :minusOne",
        ExpressionAttributeNames: { "#n": "n" },
        ExpressionAttributeValues: { ":minusOne": -1 },
      });
      expect(input.ConditionExpression).toBeUndefined();
    }
    expect([device.Key?.pk, all.Key?.pk]).toEqual([`question#${sha256(DEVICE)}#2026-10-30T10`, "question#ALL#2026-10-30T10"]);
  });

  it("gives a question taken without a device id back to the shared bucket", async () => {
    await take("question", undefined, AT_10_59, deps());

    await giveBack("question", "bad id", AT_10_59, deps());

    expect(counts.get(`question#${sha256("none")}#2026-10-30T10`)).toBe(0);
  });
});
