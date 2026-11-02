// "Try your own photo" (C534, C640): POST /try gives an upload link for a photo the person chose. It runs the same
// pipeline as a report, and its result is shown only to that person: no location, no capture time and no pin.
import { createHash } from "node:crypto";
import { ConditionalCheckFailedException, DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { S3Client } from "@aws-sdk/client-s3";
import { GetParameterCommand, type GetParameterCommandInput, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, PutCommand, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { route } from "../src/index";
import { createStopSwitch } from "../src/stopSwitch";
import { createTry } from "../src/tryPhoto";
import type { UploadDeps } from "../src/uploads";

const NOW = Date.parse("2026-10-30T10:06:40Z");
const NOW_S = NOW / 1000;
const BUCKET = "lusot-test01-uploads";
const DEVICE = "device-0123456789abcdef";

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
// A presigned POST is signed locally from the client's credentials, so these fake ones never leave the test.
const s3 = new S3Client({ region: "ap-southeast-1", credentials: { accessKeyId: "test", secretAccessKey: "test" } });
const ssm = new SSMClient({ region: "ap-southeast-1" });
const ddbMock = mockClient(ddb);
const s3Mock = mockClient(s3);
const ssmMock = mockClient(ssm);

function deps(): UploadDeps {
  return {
    ddb,
    s3,
    isStopped: createStopSwitch(ssm, "/lusot/stop/"),
    tableName: "reports",
    limitsTableName: "limits",
    bucketName: BUCKET,
    now: () => NOW,
  };
}

// The named switches read "on"; every other one reads "off".
function switchesOn(...names: string[]): void {
  ssmMock.on(GetParameterCommand).callsFake((input: GetParameterCommandInput) => {
    const name = String(input.Name).replace("/lusot/stop/", "");
    return { Parameter: { Value: names.includes(name) ? "on" : "off" } };
  });
}

function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

beforeEach(() => {
  ddbMock.reset();
  s3Mock.reset();
  ssmMock.reset();
  switchesOn();
  ddbMock.on(PutCommand).resolves({});
  ddbMock.on(UpdateCommand).resolves({});
  // The presigner reads the clock itself, so pin it to the injected now.
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("POST /try", () => {
  it("stores a pending try report with no location, capture, device or pin field, kept 7 days", async () => {
    const res = await createTry(JSON.stringify({ consentVersion: "0a1b2c3d" }), DEVICE, deps());

    expect(res.statusCode).toBe(201);
    const { reportId } = JSON.parse(res.body);
    expect(reportId).toMatch(/^r_[0-9a-f]{32}$/);
    const puts = ddbMock.commandCalls(PutCommand);
    expect(puts).toHaveLength(1);
    const { TableName, Item } = puts[0].args[0].input;
    expect(TableName).toBe("reports");
    // Exactly these fields: a try report has no lat, lng, geohash, gpsAccuracyM, nudgeM, visibleUntil or flags,
    // and never the device id (C520). Its run's time stands in for a capture time, as a sample's does.
    expect(Item).toEqual({
      pk: "TRY",
      sk: `2026-10-30T10:06:40Z#${reportId}`,
      reportId,
      mode: "try",
      status: "pending",
      consentVersion: "0a1b2c3d",
      capturedAt: "2026-10-30T10:06:40Z",
      receivedAt: "2026-10-30T10:06:40Z",
      expiresAt: NOW_S + 7 * 24 * 60 * 60,
    });
    expect(JSON.stringify(Item)).not.toContain(DEVICE);
  });

  it("returns the upload's presigned POST for raw/<reportId>.jpg: a JPEG of at most 10 MB, for 5 minutes", async () => {
    const res = await createTry(undefined, DEVICE, deps());

    expect(res.statusCode).toBe(201);
    const { reportId, upload, expiresInS } = JSON.parse(res.body);
    const key = `raw/${reportId}.jpg`;
    expect(Object.keys(JSON.parse(res.body)).sort()).toEqual(["expiresInS", "reportId", "upload"]);
    expect(expiresInS).toBe(300);
    expect(upload.fields.key).toBe(key);
    expect(upload.fields["Content-Type"]).toBe("image/jpeg");
    const policy = JSON.parse(Buffer.from(upload.fields.Policy, "base64").toString("utf8"));
    expect(policy.expiration).toBe("2026-10-30T10:11:40Z");
    expect(policy.conditions).toEqual(
      expect.arrayContaining([["content-length-range", 1, 10485760], { "Content-Type": "image/jpeg" }, { key }, { bucket: BUCKET }]),
    );
    expect(s3Mock.calls()).toHaveLength(0);
  });

  it("takes an absent or empty body, and leaves out consentVersion when it isn't sent", async () => {
    for (const body of [undefined, "", "{}"]) {
      ddbMock.resetHistory();
      const res = await createTry(body, DEVICE, deps());

      expect(res.statusCode, String(body)).toBe(201);
      expect(ddbMock.commandCalls(PutCommand)[0].args[0].input.Item, String(body)).not.toHaveProperty("consentVersion");
    }
  });

  it("answers 400 for a body that isn't a JSON object or a malformed consentVersion, before any count", async () => {
    for (const body of ["not json", "[]", "null", '"text"', JSON.stringify({ consentVersion: "has space" }), JSON.stringify({ consentVersion: 7 })]) {
      const res = await createTry(body, DEVICE, deps());

      expect(res.statusCode, body).toBe(400);
      expect(JSON.parse(res.body).error, body).toBe("bad_request");
    }
    expect(ddbMock.calls()).toHaveLength(0);
  });

  it("answers 503 uploads_paused while uploads are stopped, before it reads the model-calls switch, counts or stores", async () => {
    switchesOn("uploads", "model-calls");

    const res = await createTry(undefined, DEVICE, deps());

    expect(res.statusCode).toBe(503);
    expect(JSON.parse(res.body)).toEqual({ error: "uploads_paused" });
    expect(ssmMock.commandCalls(GetParameterCommand).map((call) => call.args[0].input.Name)).toEqual(["/lusot/stop/uploads"]);
    expect(ddbMock.calls()).toHaveLength(0);
  });

  it("answers 503 model_calls_paused while model calls are stopped (by hand, the spend stop or the credit guard), before it counts or stores", async () => {
    switchesOn("model-calls");

    const res = await createTry(undefined, DEVICE, deps());

    expect(res.statusCode).toBe(503);
    expect(JSON.parse(res.body)).toEqual({ error: "model_calls_paused" });
    expect(ddbMock.calls()).toHaveLength(0);
    expect(s3Mock.calls()).toHaveLength(0);
  });

  it("counts against the try bucket, the device's hour, the hour in all and the UTC day, and stores nothing when refused", async () => {
    const res = await createTry(undefined, DEVICE, deps());

    expect(res.statusCode).toBe(201);
    expect(ddbMock.commandCalls(UpdateCommand).map((call) => call.args[0].input.Key?.pk)).toEqual([
      `try#${sha256(DEVICE)}#2026-10-30T10`,
      "try#ALL#2026-10-30T10",
      "try#ALL#2026-10-30",
    ]);

    // Each counter refusing in turn gives its own code, and no report is stored.
    for (const [refused, error] of [
      [`try#${sha256(DEVICE)}#`, "device_limit"],
      ["try#ALL#2026-10-30T10", "global_cap"],
      ["try#ALL#2026-10-30", "daily_cap"],
    ] as const) {
      ddbMock.reset();
      ddbMock.on(PutCommand).resolves({});
      ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
        const pk = String(input.Key?.pk);
        const hit = refused.endsWith("#") ? pk.startsWith(refused) : pk === refused;
        if (input.ConditionExpression !== undefined && hit) {
          throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
        }
        return {};
      });

      const refusal = await createTry(undefined, DEVICE, deps());

      expect(refusal.statusCode, error).toBe(429);
      expect(JSON.parse(refusal.body), error).toEqual({ error });
      expect(refusal.headers["retry-after"], error).toMatch(/^\d+$/);
      expect(ddbMock.commandCalls(PutCommand), error).toHaveLength(0);
    }
  });

  it("is POST /try in the router, with X-Lusot-Device passed to the limits", async () => {
    const res = await route(
      { routeKey: "POST /try", headers: { "x-lusot-device": DEVICE }, body: "{}", isBase64Encoded: false },
      { ...deps(), indexName: "i", feedIndexName: "f", inchesShown: false } as Parameters<typeof route>[1],
    );

    expect(res.statusCode).toBe(201);
    expect(ddbMock.commandCalls(UpdateCommand)[0].args[0].input.Key?.pk).toBe(`try#${sha256(DEVICE)}#2026-10-30T10`);
  });
});
