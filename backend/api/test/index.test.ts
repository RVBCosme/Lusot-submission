import { createHash } from "node:crypto";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { S3Client } from "@aws-sdk/client-s3";
import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, PutCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { type Deps, route } from "../src/index";
import { createFeed, createMapPins } from "../src/pins";
import { createStopSwitch } from "../src/stopSwitch";

const ID = "r_0123456789abcdef0123456789abcdef";
const NOW_ISO = "2026-10-30T10:06:40Z";
const UPLOAD = JSON.stringify({ lat: 14.6095, lng: 120.9894, gpsAccuracyM: 12, capturedAt: "2026-10-30T10:05:12Z" });

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const s3 = new S3Client({ region: "ap-southeast-1", credentials: { accessKeyId: "test", secretAccessKey: "test" } });
const ssm = new SSMClient({ region: "ap-southeast-1" });
const ddbMock = mockClient(ddb);
const ssmMock = mockClient(ssm);
mockClient(s3);

function deps(): Deps {
  const base = {
    ddb,
    s3,
    isStopped: createStopSwitch(ssm, "/lusot/stop/"),
    tableName: "reports",
    limitsTableName: "limits",
    indexName: "reportId-index",
    feedIndexName: "feed-index",
    bucketName: "lusot-test01-uploads",
    inchesShown: false,
    now: () => Date.parse(NOW_ISO),
  };
  return { ...base, mapPins: createMapPins(base), feed: createFeed(base) };
}

beforeEach(() => {
  ddbMock.reset();
  ssmMock.reset();
  ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
  ddbMock.on(PutCommand).resolves({});
  ddbMock.on(UpdateCommand).resolves({});
});

describe("route", () => {
  it("unknown route gives 404", async () => {
    const res = await route({ routeKey: "GET /nope", isBase64Encoded: false }, deps());

    expect(res.statusCode).toBe(404);
    expect(JSON.parse(res.body)).toEqual({ error: "not_found" });
    expect(ddbMock.calls()).toHaveLength(0);
  });

  it("sends POST /uploads to the upload handler", async () => {
    const res = await route({ routeKey: "POST /uploads", body: UPLOAD, isBase64Encoded: false }, deps());

    expect(res.statusCode).toBe(201);
    expect(ddbMock.commandCalls(PutCommand)).toHaveLength(1);
  });

  it("passes X-Lusot-Device to the limits", async () => {
    const device = "device-0123456789abcdef";
    const headers = { "x-lusot-device": device };

    const res = await route({ routeKey: "POST /uploads", headers, body: UPLOAD, isBase64Encoded: false }, deps());

    expect(res.statusCode).toBe(201);
    // The hour comes from the clock's ISO string, so a clock passed in milliseconds fails here (F3).
    const hour = NOW_ISO.slice(0, 13);
    const keys = ddbMock.commandCalls(UpdateCommand).map((call) => call.args[0].input.Key?.pk);
    const hash = createHash("sha256").update(device).digest("hex");
    expect(keys).toEqual([`upload#${hash}#${hour}`, `upload#ALL#${hour}`]);
  });

  it("decodes a base64 body", async () => {
    const encoded = Buffer.from(UPLOAD, "utf8").toString("base64");

    const res = await route({ routeKey: "POST /uploads", body: encoded, isBase64Encoded: true }, deps());

    expect(res.statusCode).toBe(201);
  });

  it("sends GET /reports/{id} to the report handler", async () => {
    // 7 days after capture, from an ISO string (F3). Without it the report answers 404 (C526).
    const expiresAt = Date.parse("2026-11-06T10:05:12Z") / 1000;
    ddbMock.on(QueryCommand).resolves({ Items: [{ reportId: ID, status: "pending", capturedAt: "2026-10-30T10:05:12Z", expiresAt }] });

    const res = await route({ routeKey: "GET /reports/{id}", pathParameters: { id: ID }, isBase64Encoded: false }, deps());

    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body).status).toBe("pending");
  });
});
