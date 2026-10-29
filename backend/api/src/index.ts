import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { S3Client } from "@aws-sdk/client-s3";
import { SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import type { APIGatewayProxyEventV2 } from "aws-lambda";
import { type FlagDeps, flagReport } from "./flags";
import { json, type JsonResponse } from "./http";
import { logError } from "./log";
import { createFeed, createMapPins, nearby, type PinDeps } from "./pins";
import { getReport, type ReportDeps } from "./reports";
import { createStopSwitch } from "./stopSwitch";
import { createUpload, type UploadDeps } from "./uploads";

export type Deps = UploadDeps &
  ReportDeps &
  PinDeps &
  FlagDeps & {
    // Built once per container from the deps, so their memos persist (T9).
    mapPins: () => Promise<JsonResponse>;
    feed: () => Promise<JsonResponse>;
  };
// The tests' events often carry no headers, so they are optional here.
type RouteEvent = Pick<
  APIGatewayProxyEventV2,
  "routeKey" | "pathParameters" | "queryStringParameters" | "body" | "isBase64Encoded"
> &
  Partial<Pick<APIGatewayProxyEventV2, "headers">>;

export async function route(event: RouteEvent, deps: Deps): Promise<JsonResponse> {
  switch (event.routeKey) {
    case "POST /uploads":
      return createUpload(readBody(event), deviceHeader(event), deps);
    case "GET /reports/{id}":
      return getReport(event.pathParameters?.id, deps);
    case "GET /reports":
      return nearby(event.queryStringParameters, deps);
    case "GET /map/pins":
      return deps.mapPins();
    case "GET /pins.geojson":
      return deps.feed();
    case "POST /reports/{id}/flag":
      return flagReport(event.pathParameters?.id, deviceHeader(event), deps);
    default:
      return json(404, { error: "not_found" });
  }
}

// HTTP APIs base64-encode bodies whose content type isn't text.
function readBody(event: RouteEvent): string | undefined {
  if (event.body === undefined || !event.isBase64Encoded) return event.body;
  return Buffer.from(event.body, "base64").toString("utf8");
}

// The app's random device id (C508). HTTP APIs lowercase header names in payload 2.0.
function deviceHeader(event: RouteEvent): string | undefined {
  return event.headers?.["x-lusot-device"];
}

// Built on the first request and kept for the container's life, so the stop switch cache and
// the map's and the feed's memos persist.
let live: Deps | undefined;

export async function handler(event: APIGatewayProxyEventV2): Promise<JsonResponse> {
  live ??= liveDeps();
  try {
    return await route(event, live);
  } catch (err) {
    // Left uncaught, the runtime would log the whole AWS error message, ARNs included.
    logError("request_failed", err, { routeKey: event.routeKey });
    return json(500, { error: "internal" });
  }
}

function liveDeps(): Deps {
  const base = {
    ddb: DynamoDBDocumentClient.from(new DynamoDBClient({})),
    s3: new S3Client({}),
    isStopped: createStopSwitch(new SSMClient({}), env("STOP_PARAM_PREFIX")),
    tableName: env("TABLE_NAME"),
    limitsTableName: env("LIMITS_TABLE_NAME"),
    indexName: env("INDEX_NAME"),
    feedIndexName: env("FEED_INDEX_NAME"),
    bucketName: env("BUCKET_NAME"),
    // C515: a literal in the template; only "true" shows inches.
    inchesShown: env("INCHES_SHOWN") === "true",
    now: Date.now,
  };
  return { ...base, mapPins: createMapPins(base), feed: createFeed(base) };
}

function env(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`missing environment variable ${name}`);
  return value;
}
