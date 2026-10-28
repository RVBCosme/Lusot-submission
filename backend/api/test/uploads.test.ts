import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { S3Client } from "@aws-sdk/client-s3";
import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, PutCommand } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createStopSwitch } from "../src/stopSwitch";
import { createUpload, type UploadDeps } from "../src/uploads";

const NOW = Date.parse("2026-10-30T10:06:40Z");
const CAPTURED_AT = "2026-10-30T10:05:12Z";
const BUCKET = "lusot-test01-uploads";

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

beforeEach(() => {
  ddbMock.reset();
  s3Mock.reset();
  ssmMock.reset();
  ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
  ddbMock.on(PutCommand).resolves({});
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
    const res = await createUpload(body({ capturedAt: "2026-10-30T18:05:12+08:00" }), deps());

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
    const res = await createUpload(body(), deps());

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
    const first = JSON.parse((await createUpload(body(), deps())).body).reportId;
    const second = JSON.parse((await createUpload(body(), deps())).body).reportId;

    expect(first).toMatch(/^r_[0-9a-f]{32}$/);
    expect(second).toMatch(/^r_[0-9a-f]{32}$/);
    expect(second).not.toBe(first);
  });

  it("rejects capture older than 15 minutes", async () => {
    const old = await createUpload(capturedAgo(15 * 60_000 + 1_000), deps());
    expect(old.statusCode).toBe(422);
    expect(JSON.parse(old.body)).toEqual({ error: "capture_too_old" });

    const ahead = await createUpload(capturedAgo(-(2 * 60_000 + 1_000)), deps());
    expect(ahead.statusCode).toBe(422);
    expect(JSON.parse(ahead.body)).toEqual({ error: "capture_in_future" });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);

    // Both edges of the window are inside it.
    expect((await createUpload(capturedAgo(15 * 60_000), deps())).statusCode).toBe(201);
    expect((await createUpload(capturedAgo(-2 * 60_000), deps())).statusCode).toBe(201);
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
  ])("rejects bad coordinates or body: %s", async (_name, raw) => {
    const res = await createUpload(raw, deps());

    expect(res.statusCode).toBe(400);
    expect(JSON.parse(res.body)).toEqual({ error: "bad_request", detail: expect.any(String) });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
  });

  it("accepts gpsAccuracyM from 0 to 10000", async () => {
    expect((await createUpload(body({ gpsAccuracyM: 0 }), deps())).statusCode).toBe(201);
    expect((await createUpload(body({ gpsAccuracyM: 10_000 }), deps())).statusCode).toBe(201);
  });

  it("returns 503 when the uploads stop switch is on", async () => {
    ssmMock.on(GetParameterCommand, { Name: "/lusot/stop/uploads" }).resolves({ Parameter: { Value: "on" } });

    const res = await createUpload(body(), deps());

    expect(res.statusCode).toBe(503);
    expect(JSON.parse(res.body)).toEqual({ error: "uploads_paused" });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
  });

  it("fails closed when the stop switch can't be read", async () => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    ssmMock.on(GetParameterCommand).rejects(new Error("ssm unavailable"));

    const res = await createUpload(body(), deps());

    expect(res.statusCode).toBe(503);
    expect(JSON.parse(res.body)).toEqual({ error: "uploads_paused" });
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(0);
    expect(logged).toHaveBeenCalledOnce();
  });
});
