import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { S3Client } from "@aws-sdk/client-s3";
import { SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import type { APIGatewayProxyEventV2 } from "aws-lambda";
import { json, type JsonResponse } from "./http";
import { logError } from "./log";
import { getReport, type ReportDeps } from "./reports";
import { createStopSwitch } from "./stopSwitch";
import { createUpload, type UploadDeps } from "./uploads";

export type Deps = UploadDeps & ReportDeps;
type RouteEvent = Pick<APIGatewayProxyEventV2, "routeKey" | "pathParameters" | "body" | "isBase64Encoded">;

export async function route(event: RouteEvent, deps: Deps): Promise<JsonResponse> {
  switch (event.routeKey) {
    case "POST /uploads":
      return createUpload(readBody(event), deps);
    case "GET /reports/{id}":
      return getReport(event.pathParameters?.id, deps);
    default:
      return json(404, { error: "not_found" });
  }
}

// HTTP APIs base64-encode bodies whose content type isn't text.
function readBody(event: RouteEvent): string | undefined {
  if (event.body === undefined || !event.isBase64Encoded) return event.body;
  return Buffer.from(event.body, "base64").toString("utf8");
}

// Built on the first request and kept for the container's life, so the stop switch cache persists.
let live: Deps | undefined;

export async function handler(event: APIGatewayProxyEventV2): Promise<JsonResponse> {
  live ??= {
    ddb: DynamoDBDocumentClient.from(new DynamoDBClient({})),
    s3: new S3Client({}),
    isStopped: createStopSwitch(new SSMClient({}), env("STOP_PARAM_PREFIX")),
    tableName: env("TABLE_NAME"),
    indexName: env("INDEX_NAME"),
    bucketName: env("BUCKET_NAME"),
    now: Date.now,
  };
  try {
    return await route(event, live);
  } catch (err) {
    // Left uncaught, the runtime would log the whole AWS error message, ARNs included.
    logError("request_failed", err, { routeKey: event.routeKey });
    return json(500, { error: "internal" });
  }
}

function env(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`missing environment variable ${name}`);
  return value;
}
