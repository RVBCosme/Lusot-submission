import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { S3Client } from "@aws-sdk/client-s3";
import { SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import type { APIGatewayProxyEventV2 } from "aws-lambda";
import { type AskDeps, type AskRequest, askTyped, askVoice, createSpendDdb, NCR_BOUNDS, SPEND_CLIENT_CONFIG } from "./ask/handler";
import { logAsk } from "./ask/log";
import { createMeta } from "./ask/meta";
import { createGeocoder } from "./ask/nominatim";
import { SPOTS } from "./ask/spots";
import { type FlagDeps, flagReport } from "./flags";
import { json, type JsonResponse } from "./http";
import { logError } from "./log";
import { inMetroManila } from "./metroManila";
import { createModelKey } from "./modelKey";
import { createFeed, createMapPins, nearby, nearbyPins, type PinDeps } from "./pins";
import { getReport, type ReportDeps } from "./reports";
import { createManifest, listSamples, runSample, type SampleDeps } from "./samples";
import { createStopSwitch } from "./stopSwitch";
import { createUpload, type UploadDeps } from "./uploads";

export type Deps = UploadDeps &
  ReportDeps &
  PinDeps &
  FlagDeps &
  SampleDeps & {
    // Built once per container from the deps, so their memos persist (T9), as SampleDeps' manifest is.
    mapPins: () => Promise<JsonResponse>;
    feed: () => Promise<JsonResponse>;
    // Ask Lusot's deps, built on the first question only (its C701), so no other route reads the model key or
    // Ask's two variables. Optional, so deps built by hand for MS4's routes need none.
    ask?: () => AskDeps;
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
    case "GET /samples":
      return listSamples(deps);
    case "POST /samples/{sampleId}":
      return runSample(event.pathParameters?.sampleId, deviceHeader(event), deps);
    case "POST /ask":
      return askRoute(event, deps, "ask", askTyped);
    case "POST /ask/voice":
      return askRoute(event, deps, "ask_voice", askVoice);
    default:
      return json(404, { error: "not_found" });
  }
}

// A missing Ask variable answers MS1's 500 internal, and its line names the variable, never a value.
async function askRoute(
  event: RouteEvent,
  deps: Deps,
  route: "ask" | "ask_voice",
  answer: (req: AskRequest, deps: AskDeps) => Promise<JsonResponse>,
): Promise<JsonResponse> {
  let askDeps: AskDeps;
  try {
    if (deps.ask === undefined) throw new Error("Ask Lusot's deps were not given");
    askDeps = deps.ask();
  } catch (err) {
    if (!(err instanceof MissingVariable)) throw err;
    console.error(JSON.stringify({ msg: "ask_unconfigured", variable: err.variable }));
    logAsk({ route, status: 500, code: "internal", error: err.name });
    return json(500, { error: "internal" });
  }
  return answer({ body: readBody(event), device: deviceHeader(event) }, askDeps);
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
// the map's, the feed's and the manifest's memos persist.
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
  let built: AskDeps | undefined;
  return {
    ...base,
    mapPins: createMapPins(base),
    feed: createFeed(base),
    manifest: createManifest(base),
    // Kept once built. A build that throws keeps nothing, so the next question tries again.
    ask: () => (built ??= askDeps(base)),
  };
}

// Ask Lusot's deps. Its two variables are read here, on its own routes only, so MS4's routes never need them.
function askDeps(base: PinDeps & { limitsTableName: string }): AskDeps {
  const modelKeyParam = env("MODEL_KEY_PARAM");
  const userAgent = env("NOMINATIM_USER_AGENT");
  // The key's read and the spend path's SSM calls (the stop's read, the pause) get the spend client's bounds.
  const ssm = new SSMClient(SPEND_CLIENT_CONFIG);
  const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));
  return {
    ddb: base.ddb,
    limitsTableName: base.limitsTableName,
    isStopped: base.isStopped,
    nearbyPins: (lat, lng, radiusM) => nearbyPins({ lat, lng }, radiusM, base),
    inMetroManila,
    spots: SPOTS,
    geocoder: createGeocoder({
      ddb: base.ddb,
      limitsTableName: base.limitsTableName,
      fetchFn: fetch,
      userAgent,
      isStopped: base.isStopped,
      now: base.now,
      sleep,
      bounds: NCR_BOUNDS,
    }),
    modelKey: createModelKey(ssm, modelKeyParam),
    createMeta,
    spendDdb: createSpendDdb(),
    ssm,
    stopParamPrefix: env("STOP_PARAM_PREFIX"),
    now: base.now,
    sleep,
    random: Math.random,
  };
}

// Its message names the variable, never a value.
class MissingVariable extends Error {
  constructor(readonly variable: string) {
    super(`missing environment variable ${variable}`);
    this.name = "MissingVariable";
  }
}

function env(name: string): string {
  const value = process.env[name];
  if (!value) throw new MissingVariable(name);
  return value;
}
