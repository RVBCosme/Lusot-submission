import { GetParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, PutCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";
import type { APIGatewayProxyEventV2 } from "aws-lambda";
import { mockClient } from "aws-sdk-client-mock";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { handler } from "../src/index";
import { awsError } from "./awsError";

// The handler builds its own clients from the environment, so mock the client classes.
const ddbMock = mockClient(DynamoDBDocumentClient);
const ssmMock = mockClient(SSMClient);
const UPLOAD = JSON.stringify({ lat: 14.6095, lng: 120.9894, gpsAccuracyM: 12, capturedAt: new Date().toISOString() });

beforeAll(() => {
  vi.stubEnv("AWS_REGION", "ap-southeast-1");
  vi.stubEnv("TABLE_NAME", "reports");
  vi.stubEnv("INDEX_NAME", "reportId-index");
  vi.stubEnv("BUCKET_NAME", "lusot-test01-uploads");
  vi.stubEnv("STOP_PARAM_PREFIX", "/lusot/stop/");
  vi.stubEnv("LIMITS_TABLE_NAME", "limits");
  vi.stubEnv("FEED_INDEX_NAME", "feed-index");
  vi.stubEnv("INCHES_SHOWN", "false");
});

afterEach(() => {
  ddbMock.reset();
  ssmMock.reset();
  vi.restoreAllMocks();
});

afterAll(() => {
  vi.unstubAllEnvs();
});

describe("handler", () => {
  it.each([
    ["POST /uploads", { routeKey: "POST /uploads", body: UPLOAD, isBase64Encoded: false }],
    ["GET /reports/{id}", { routeKey: "GET /reports/{id}", pathParameters: { id: "r_0123456789abcdef0123456789abcdef" }, isBase64Encoded: false }],
  ])("a failed AWS call on %s gives 500 and logs no ARN", async (routeKey, event) => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    ssmMock.on(GetParameterCommand).resolves({ Parameter: { Value: "off" } });
    ddbMock.on(PutCommand).rejects(awsError("AccessDeniedException", 400));
    ddbMock.on(QueryCommand).rejects(awsError("AccessDeniedException", 400));

    const res = await handler(event as APIGatewayProxyEventV2);

    expect(res.statusCode).toBe(500);
    expect(JSON.parse(res.body)).toEqual({ error: "internal" });
    expect(logged).toHaveBeenCalledOnce();
    const line = logged.mock.calls[0][0] as string;
    expect(line).not.toContain("arn:");
    expect(JSON.parse(line)).toEqual({ msg: "request_failed", routeKey, error: "AccessDeniedException", status: 400 });
  });
});
