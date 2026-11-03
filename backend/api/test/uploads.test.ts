import { createHash } from "node:crypto";
import { ConditionalCheckFailedException, DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { S3Client } from "@aws-sdk/client-s3";
import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, PutCommand, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createStopSwitch } from "../src/stopSwitch";
import { createUpload, type UploadDeps } from "../src/uploads";

const NOW = Date.parse("2026-10-30T10:06:40Z");
const CAPTURED_AT = "2026-10-30T10:05:12Z";
const BUCKET = "lusot-test01-uploads";
const DEVICE = "device-0123456789abcdef";
const BATANGAS = { lat: 13.7565, lng: 121.0583 };

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

function body(fields: Record<string, unknown> = {}): string {
  return JSON.stringify({ lat: 14.6095, lng: 120.9894, gpsAccuracyM: 12, capturedAt: CAPTURED_AT, ...fields });
}

function capturedAgo(ms: number): string {
  return body({ capturedAt: new Date(NOW - ms).toISOString() });
}

function storedItem(): Record<string, unknown> {
  const puts = ddbMock.commandCalls(PutCommand);
  expect(puts).toHaveLength(1);
  return puts[0].args[0].input.Item ?? {};
}

// The mock never evaluates a condition, so refuse the device's or the hour's counter by its key.
function refuseLimits(refuse: { device?: boolean; all?: boolean }): void {
  ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
    const all = String(input.Key?.pk).includes("#ALL#");
    if (input.ConditionExpression !== undefined && (all ? refuse.all : refuse.device)) {
      throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
    }
    return {};
  });
}

beforeEach(() => {
  ddbMock.reset();
  s3Mock.reset();
  ssmMock.reset();
  ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
  ddbMock.on(PutCommand).resolves({});
  ddbMock.on(UpdateCommand).resolves({});
  // The presigner reads the clock itself, so pin it to the injected now.
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("POST /uploads", () => {
  it("creates a pending live report with geohash pk and TTLs", async () => {
    // A Manila phone clock; Table 14 stores capture times in UTC.
    const res = await createUpload(body({ capturedAt: "2026-10-30T18:05:12+08:00" }), DEVICE, deps());

    expect(res.statusCode).toBe(201);
    const puts = ddbMock.commandCalls(PutCommand);
    expect(puts).toHaveLength(1);
    const { TableName, Item } = puts[0].args[0].input;
    const reportId = JSON.parse(res.body).reportId;
    const capturedAtEpoch = Date.parse(CAPTURED_AT) / 1000;
    expect(TableName).toBe("reports");
    expect(Item).toEqual({
      pk: "GEO#wdw515",
      sk: `${CAPTURED_AT}#${reportId}`,
      reportId,
      mode: "live",
      status: "pending",
      lat: 14.6095,
      lng: 120.9894,
      gpsAccuracyM: 12,
      nudgeM: 0,
      capturedAt: CAPTURED_AT,
      receivedAt: "2026-10-30T10:06:40Z",
      flags: 0,
      visibleUntil: capturedAtEpoch + 10800,
      expiresAt: capturedAtEpoch + 604800,
    });
    expect(Item?.sk.startsWith(Item.capturedAt)).toBe(true);
  });

  it("returns a presigned POST for raw/<reportId>.jpg", async () => {
    const res = await createUpload(body(), DEVICE, deps());

    expect(res.statusCode).toBe(201);
    const { reportId, upload, expiresInS } = JSON.parse(res.body);
    const key = `raw/${reportId}.jpg`;
    expect(expiresInS).toBe(300);
    expect(upload.fields.key).toBe(key);
    expect(upload.fields["Content-Type"]).toBe("image/jpeg");
    // S3 enforces the signed policy, so check the policy itself.
    const policy = JSON.parse(Buffer.from(upload.fields.Policy, "base64").toString("utf8"));
    expect(policy.expiration).toBe("2026-10-30T10:11:40Z");
    expect(policy.conditions).toEqual(
      expect.arrayContaining([
        ["content-length-range", 1, 10485760],
        { "Content-Type": "image/jpeg" },
        { key },
        { bucket: BUCKET },
      ]),
    );
    expect(s3Mock.calls()).toHaveLength(0);
  });

  it("report ids are r_ plus 32 hex", async () => {
    const first = JSON.parse((await createUpload(body(), DEVICE, deps())).body).reportId;
    const second = JSON.parse((await createUpload(body(), DEVICE, deps())).body).reportId;

    expect(first).toMatch(/^r_[0-9a-f]{32}$/);
    expect(second).toMatch(/^r_[0-9a-f]{32}$/);
    expect(second).not.toBe(first);
  });

  it("rejects capture older than 15 minutes", async () => {
    const old = await createUpload(capturedAgo(15 * 60_000 + 1_000), DEVICE, deps());
    expect(old.statusCode).toBe(422);
    expect(JSON.parse(old.body)).toEqual({ error: "capture_too_old" });

    const ahead = await createUpload(capturedAgo(-(2 * 60_000 + 1_000)), DEVICE, deps());
    expect(ahead.statusCode).toBe(422);
    expect(JSON.parse(ahead.body)).toEqual({ error: "capture_in_future" });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);

    // Both edges of the window are inside it.
    expect((await createUpload(capturedAgo(15 * 60_000), DEVICE, deps())).statusCode).toBe(201);
    expect((await createUpload(capturedAgo(-2 * 60_000), DEVICE, deps())).statusCode).toBe(201);
  });

  it.each([
    ["missing lat", JSON.stringify({ lng: 120.9894, gpsAccuracyM: 12, capturedAt: CAPTURED_AT })],
    ["lat = 91", body({ lat: 91 })],
    ['lng = "x"', body({ lng: "x" })],
    ["a non-JSON body", "not json"],
    ["no body", undefined],
    ["a JSON body that isn't an object", "null"],
    ["gpsAccuracyM below 0", body({ gpsAccuracyM: -1 })],
    ["gpsAccuracyM above 10000", body({ gpsAccuracyM: 10_001 })],
    ["capturedAt without a time zone", body({ capturedAt: "2026-10-30T10:05:12" })],
    ["capturedAt that isn't a time", body({ capturedAt: "yesterday" })],
    ["nudgeM below 0", body({ nudgeM: -1 })],
    ['nudgeM "x"', body({ nudgeM: "x" })],
    ["consentVersion 7", body({ consentVersion: 7 })],
    ['consentVersion ""', body({ consentVersion: "" })],
  ])("rejects bad coordinates or body: %s", async (_name, raw) => {
    const res = await createUpload(raw, DEVICE, deps());

    expect(res.statusCode).toBe(400);
    expect(JSON.parse(res.body)).toEqual({ error: "bad_request", detail: expect.any(String) });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
    expect(ddbMock.commandCalls(UpdateCommand)).toHaveLength(0);
  });

  it("accepts gpsAccuracyM from 0 to 50", async () => {
    expect((await createUpload(body({ gpsAccuracyM: 0 }), DEVICE, deps())).statusCode).toBe(201);
    expect((await createUpload(body({ gpsAccuracyM: 50 }), DEVICE, deps())).statusCode).toBe(201);
  });

  it("refuses gpsAccuracyM above 50 with 422 gps_too_coarse", async () => {
    for (const gpsAccuracyM of [50.5, 10_000]) {
      const res = await createUpload(body({ gpsAccuracyM }), DEVICE, deps());

      expect(res.statusCode).toBe(422);
      expect(JSON.parse(res.body)).toEqual({ error: "gps_too_coarse" });
    }
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
    expect(ddbMock.commandCalls(UpdateCommand)).toHaveLength(0);
  });

  it("takes nudgeM from 0 to 100, defaults it to 0, and refuses 100.5 with 422 nudge_too_far", async () => {
    for (const [fields, stored] of [
      [{ nudgeM: 0 }, 0],
      [{ nudgeM: 37.5 }, 37.5],
      [{ nudgeM: 100 }, 100],
      [{}, 0],
    ] as const) {
      ddbMock.resetHistory();
      expect((await createUpload(body(fields), DEVICE, deps())).statusCode).toBe(201);
      expect(storedItem().nudgeM).toBe(stored);
    }

    ddbMock.resetHistory();
    const far = await createUpload(body({ nudgeM: 100.5 }), DEVICE, deps());
    expect(far.statusCode).toBe(422);
    expect(JSON.parse(far.body)).toEqual({ error: "nudge_too_far" });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
  });

  it("stores consentVersion when sent", async () => {
    await createUpload(body({ consentVersion: "0a1b2c3d" }), DEVICE, deps());
    expect(storedItem().consentVersion).toBe("0a1b2c3d");

    // Absent, it isn't written at all: the document client refuses an undefined attribute.
    ddbMock.resetHistory();
    await createUpload(body(), DEVICE, deps());
    expect(storedItem()).not.toHaveProperty("consentVersion");
  });

  it("sets live inside Metro Manila and private outside, whatever the nudge", async () => {
    for (const nudgeM of [0, 80]) {
      ddbMock.resetHistory();
      await createUpload(body({ nudgeM }), DEVICE, deps());
      expect(storedItem().mode).toBe("live");

      ddbMock.resetHistory();
      await createUpload(body({ ...BATANGAS, nudgeM }), DEVICE, deps());
      expect(storedItem()).toMatchObject({ mode: "private", lat: BATANGAS.lat, lng: BATANGAS.lng });
    }
  });

  it("checks the switch, then the body, then the device, then the hour's cap", async () => {
    // The switch comes before the body.
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/uploads" }).resolves({ Parameter: { Value: "on" } });
    const paused = await createUpload("not json", DEVICE, deps());
    expect(paused.statusCode).toBe(503);
    expect(JSON.parse(paused.body)).toEqual({ error: "uploads_paused" });
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/uploads" }).resolves({ Parameter: { Value: "off" } });

    // The body, its 422s included, comes before the device, and costs no limits write.
    refuseLimits({ device: true, all: true });
    const bad = await createUpload(body({ lat: 91 }), DEVICE, deps());
    expect(bad.statusCode).toBe(400);
    expect(ddbMock.commandCalls(UpdateCommand)).toHaveLength(0);
    for (const [raw, error] of [
      [capturedAgo(16 * 60_000), "capture_too_old"],
      [capturedAgo(-3 * 60_000), "capture_in_future"],
      [body({ gpsAccuracyM: 51 }), "gps_too_coarse"],
      [body({ nudgeM: 100.5 }), "nudge_too_far"],
    ]) {
      const res = await createUpload(raw, DEVICE, deps());
      expect({ status: res.statusCode, body: JSON.parse(res.body) }).toEqual({ status: 422, body: { error } });
      expect(ddbMock.commandCalls(UpdateCommand)).toHaveLength(0);
    }

    // The device comes before the hour's cap, which it never reaches.
    const device = await createUpload(body(), DEVICE, deps());
    expect(device.statusCode).toBe(429);
    expect(JSON.parse(device.body)).toEqual({ error: "device_limit" });
    expect(ddbMock.commandCalls(UpdateCommand).map((call) => call.args[0].input.Key?.pk)).toEqual([
      `upload#${createHash("sha256").update(DEVICE).digest("hex")}#2026-10-30T10`,
    ]);

    // Then the hour's cap.
    ddbMock.resetHistory();
    refuseLimits({ all: true });
    const cap = await createUpload(body(), DEVICE, deps());
    expect(cap.statusCode).toBe(429);
    expect(JSON.parse(cap.body)).toEqual({ error: "global_cap" });
    expect(cap.headers["retry-after"]).toBe("3200");
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
  });

  // Codex finding 3: a day of paid analyses used up by chosen photos and samples can't be had by an upload instead.
  it("refuses an upload when the shared day of paid analyses is full, with global_cap and no item or upload link", async () => {
    ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
      if (input.ConditionExpression !== undefined && input.Key?.pk === "analysis#ALL#2026-10-30") {
        throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
      }
      return {};
    });

    const res = await createUpload(body(), DEVICE, deps());

    expect(res.statusCode).toBe(429);
    expect(JSON.parse(res.body)).toEqual({ error: "global_cap" });
    // The seconds left in the UTC day at 10:06:40.
    expect(res.headers["retry-after"]).toBe(String(Date.parse("2026-10-31T00:00:00Z") / 1000 - Date.parse("2026-10-30T10:06:40Z") / 1000));
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
    expect(res.body).not.toContain("upload");
  });

  it("never stores a device id on the report", async () => {
    await createUpload(body(), DEVICE, deps());

    const stored = JSON.stringify(storedItem());
    expect(stored).not.toContain(DEVICE);
    expect(stored).not.toContain(createHash("sha256").update(DEVICE).digest("hex"));
  });

  it("returns 503 when the uploads stop switch is on", async () => {
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/uploads" }).resolves({ Parameter: { Value: "on" } });

    const res = await createUpload(body(), DEVICE, deps());

    expect(res.statusCode).toBe(503);
    expect(JSON.parse(res.body)).toEqual({ error: "uploads_paused" });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
  });

  it("fails closed when the stop switch can't be read", async () => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    ssmMock.on(GetParameterCommand).rejects(new Error("ssm unavailable"));

    const res = await createUpload(body(), DEVICE, deps());

    expect(res.statusCode).toBe(503);
    expect(JSON.parse(res.body)).toEqual({ error: "uploads_paused" });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
    expect(logged).toHaveBeenCalledOnce();
  });
});
