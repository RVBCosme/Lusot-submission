import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { S3Client } from "@aws-sdk/client-s3";
import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, PutCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import { beforeEach, describe, expect, it } from "vitest";
import { type Deps, route } from "../src/index";
import { createStopSwitch } from "../src/stopSwitch";

const ID = "r_0123456789abcdef0123456789abcdef";
const UPLOAD = JSON.stringify({ lat: 14.6095, lng: 120.9894, gpsAccuracyM: 12, capturedAt: "2026-10-30T10:05:12Z" });

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const s3 = new S3Client({ region: "ap-southeast-1", credentials: { accessKeyId: "test", secretAccessKey: "test" } });
const ssm = new SSMClient({ region: "ap-southeast-1" });
const ddbMock = mockClient(ddb);
const ssmMock = mockClient(ssm);
mockClient(s3);

function deps(): Deps {
  return {
    ddb,
    s3,
    isStopped: createStopSwitch(ssm, "/lusot/stop/"),
    tableName: "reports",
    indexName: "reportId-index",
    bucketName: "lusot-test01-uploads",
    now: () => Date.parse("2026-10-30T10:06:40Z"),
  };
}

beforeEach(() => {
  ddbMock.reset();
  ssmMock.reset();
  ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
  ddbMock.on(PutCommand).resolves({});
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

  it("decodes a base64 body", async () => {
    const encoded = Buffer.from(UPLOAD, "utf8").toString("base64");

    const res = await route({ routeKey: "POST /uploads", body: encoded, isBase64Encoded: true }, deps());

    expect(res.statusCode).toBe(201);
  });

  it("sends GET /reports/{id} to the report handler", async () => {
    ddbMock.on(QueryCommand).resolves({ Items: [{ reportId: ID, status: "pending", capturedAt: "2026-10-30T10:05:12Z" }] });

    const res = await route({ routeKey: "GET /reports/{id}", pathParameters: { id: ID }, isBase64Encoded: false }, deps());

    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body).status).toBe("pending");
  });
});
