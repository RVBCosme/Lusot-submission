// The handler's nine routes over class mocks, for handler.test.ts and copy.test.ts (Task 10): the
// environment it builds from, a new container per call, each route's event, and a success answer for
// every AWS call the routes make, Ask Lusot's Muse Spark calls included.
import { readFileSync } from "node:fs";
import { CopyObjectCommand, GetObjectCommand, type GetObjectCommandOutput, S3Client } from "@aws-sdk/client-s3";
import { GetParameterCommand, type GetParameterCommandInput, PutParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import {
  DynamoDBDocumentClient,
  GetCommand,
  type GetCommandInput,
  PutCommand,
  QueryCommand,
  type QueryCommandInput,
  TransactWriteCommand,
  UpdateCommand,
} from "@aws-sdk/lib-dynamodb";
import type { APIGatewayProxyEventV2 } from "aws-lambda";
import { mockClient } from "aws-sdk-client-mock";
import { vi } from "vitest";
import type { handler } from "../src/index";

// Class mocks, so the clients the handler builds for itself answer from them.
export const ddbMock = mockClient(DynamoDBDocumentClient);
export const s3Mock = mockClient(S3Client);
export const ssmMock = mockClient(SSMClient);

// index.ts's route() and test_template.py's test_routes_match_the_api_router hold these nine.
export const ROUTE_KEYS = [
  "POST /uploads",
  "GET /reports/{id}",
  "GET /reports",
  "GET /map/pins",
  "GET /pins.geojson",
  "POST /reports/{id}/flag",
  "GET /samples",
  "POST /samples/{sampleId}",
  "POST /ask",
] as const;
export type RouteKey = (typeof ROUTE_KEYS)[number];

// The seven names env() reads for every route. NODE_OPTIONS is only set by the template, and Ask Lusot's two
// (MODEL_KEY_PARAM, NOMINATIM_USER_AGENT) are read on its own route only.
export const ENV_NAMES = [
  "TABLE_NAME",
  "INDEX_NAME",
  "BUCKET_NAME",
  "STOP_PARAM_PREFIX",
  "LIMITS_TABLE_NAME",
  "FEED_INDEX_NAME",
  "INCHES_SHOWN",
] as const;

export const NOW = "2026-10-30T10:06:40Z";
export const BUCKET = "lusot-test01-uploads";
export const ID = "r_0123456789abcdef0123456789abcdef";
export const DEMO_ID = "r_fedcba9876543210fedcba9876543210";
export const SAMPLE_ID = "s0123456789";
export const DEVICE = "device-0123456789abcdef";
const CAPTURED_AT = "2026-10-30T10:05:12Z";

// A published live knee pin as the analysis Lambda leaves it, with its photo, overlay and layers.
// Its 3 h and 7 days are from ISO strings (F3).
export const PIN: Record<string, unknown> = {
  pk: "GEO#wdw515",
  sk: `${CAPTURED_AT}#${ID}`,
  reportId: ID,
  mode: "live",
  status: "done",
  capturedAt: CAPTURED_AT,
  receivedAt: "2026-10-30T10:05:20Z",
  lat: 14.6095,
  lng: 120.9894,
  gpsAccuracyM: 12,
  nudgeM: 0,
  noFloodSeen: false,
  level: "knee",
  landmark: "rim_three_quarters",
  passability: "NPLV",
  levelIsFloor: false,
  levelFrom: "geometry",
  basis: { vehicles: 1, people: 1 },
  depthInMin: 17.3,
  depthInMax: 19.1,
  readings: [
    { id: 1, kind: "wheel", landmark: "rim_three_quarters", level: "knee", levelIsFloor: false, inches: [17.3, 19.1], used: true, dropped: null },
    { id: 2, kind: "body", landmark: "not_visible", level: null, levelIsFloor: null, inches: null, used: false, dropped: null },
  ],
  photoKey: `blurred/${ID}.jpg`,
  overlayKey: `overlay/${ID}.jpg`,
  layersKey: `overlay/${ID}.json`,
  published: true,
  feedPart: "live",
  flags: 0,
  visibleUntil: Date.parse("2026-10-30T13:05:12Z") / 1000,
  expiresAt: Date.parse("2026-11-06T10:05:12Z") / 1000,
};

// A demo pin in the same cell, visible to the end of its --until day in Manila.
export const DEMO_PIN: Record<string, unknown> = {
  ...PIN,
  sk: `2026-07-24T02:30:00Z#${DEMO_ID}`,
  reportId: DEMO_ID,
  mode: "demo",
  feedPart: "demo",
  capturedAt: "2026-07-24T02:30:00Z",
  lat: 14.6097,
  lng: 120.9896,
  photoKey: `demo/blurred/${DEMO_ID}.jpg`,
  overlayKey: `demo/overlay/${DEMO_ID}.jpg`,
  layersKey: `demo/overlay/${DEMO_ID}.json`,
  credit: "Photo by a donor, faces and plates blurred by Lusot",
  place: "Rizal Avenue, Manila",
  event: "Typhoon Carina",
  visibleUntil: Date.parse("2026-11-08T23:59:59+08:00") / 1000,
  expiresAt: Date.parse("2026-11-15T23:59:59+08:00") / 1000,
};

// samples/manifest.json as samples.py writes it, with one level sample.
export const MANIFEST = {
  version: 1,
  samples: [
    {
      sampleId: SAMPLE_ID,
      credit: "Photo by a donor, faces and plates blurred by Lusot",
      license: "used with permission",
      place: "Rizal Avenue, Manila",
      date: "2026-07-24",
      event: "Typhoon Carina",
      savedAt: "2026-10-31",
      status: "done",
      noFloodSeen: false,
      level: "knee",
      landmark: "rim_three_quarters",
      passability: "NPLV",
      levelIsFloor: false,
    },
  ],
};

export const UPLOAD = { lat: 14.6095, lng: 120.9894, gpsAccuracyM: 12, capturedAt: CAPTURED_AT };

// Ask Lusot's: the model key's parameter, and a location at PIN's spot.
export const MODEL_KEY_PARAM = "/lusot/meta/model-api-key";
export const ASK_HERE = { lat: 14.6095, lng: 120.9894, accuracyM: 20 };

// Each route's request, which the success answers below take to a 200 or a 201.
const ROUTE_EVENTS: Record<RouteKey, Partial<APIGatewayProxyEventV2>> = {
  "POST /uploads": { body: JSON.stringify(UPLOAD) },
  "GET /reports/{id}": { pathParameters: { id: ID } },
  "GET /reports": { queryStringParameters: { lat: "14.6095", lng: "120.9894" } },
  "GET /map/pins": {},
  "GET /pins.geojson": {},
  "POST /reports/{id}/flag": { pathParameters: { id: ID } },
  "GET /samples": {},
  "POST /samples/{sampleId}": { pathParameters: { sampleId: SAMPLE_ID } },
  "POST /ask": { body: JSON.stringify({ question: "May baha ba dito?", here: ASK_HERE }) },
};

// An HTTP API payload 2.0 event, as API Gateway sends it to the handler.
export function request(routeKey: string, fields: Partial<APIGatewayProxyEventV2> = {}): APIGatewayProxyEventV2 {
  const [method, path] = routeKey.split(" ");
  return {
    version: "2.0",
    routeKey,
    rawPath: path,
    rawQueryString: "",
    headers: { "x-lusot-device": DEVICE },
    isBase64Encoded: false,
    requestContext: { http: { method, path, protocol: "HTTP/1.1", sourceIp: "198.51.100.20", userAgent: "lusot-test" } },
    ...ROUTE_EVENTS[routeKey as RouteKey],
    ...fields,
  } as APIGatewayProxyEventV2;
}

// The environment the handler builds from. The presigners sign from credentials that CI doesn't
// have, so these fake ones stand in. With AWS_PROFILE set, the SDK would skip them for the profile.
export function stubApiEnv(): void {
  vi.stubEnv("AWS_REGION", "ap-southeast-1");
  vi.stubEnv("AWS_ACCESS_KEY_ID", "test");
  vi.stubEnv("AWS_SECRET_ACCESS_KEY", "test");
  vi.stubEnv("AWS_PROFILE", undefined);
  vi.stubEnv("TABLE_NAME", "reports");
  vi.stubEnv("INDEX_NAME", "reportId-index");
  vi.stubEnv("BUCKET_NAME", BUCKET);
  vi.stubEnv("STOP_PARAM_PREFIX", "/lusot/stop/");
  vi.stubEnv("LIMITS_TABLE_NAME", "limits");
  vi.stubEnv("FEED_INDEX_NAME", "feed-index");
  vi.stubEnv("INCHES_SHOWN", "false");
  vi.stubEnv("MODEL_KEY_PARAM", MODEL_KEY_PARAM);
  vi.stubEnv("NOMINATIM_USER_AGENT", "Lusot/1.0 (test)");
}

// The handler of a new container, so no switch cache or memo carries over from an earlier call.
export async function coldHandler(): Promise<typeof handler> {
  vi.resetModules();
  return (await import("../src/index")).handler;
}

export function resetMocks(): void {
  ddbMock.reset();
  s3Mock.reset();
  ssmMock.reset();
  vi.unstubAllGlobals();
}

// GetObject's Body is a stream with the SDK's transformToString, the one method the code reads.
function objectBody(value: unknown): GetObjectCommandOutput["Body"] {
  const text = JSON.stringify(value);
  return { transformToString: async () => text } as unknown as GetObjectCommandOutput["Body"];
}

export interface Serve {
  // The items the table holds. The mock never evaluates an expression, so each query answers by its values.
  stored?: Record<string, unknown>[];
  // The stop switches that are set, by name.
  stopped?: string[];
  // Runs before every DynamoDB and S3 answer, so a test can fail any one of them.
  before?: () => void;
}

// A success answer for every AWS call the nine routes make, and Muse Spark's for Ask.
export function serve({ stored = [PIN, DEMO_PIN], stopped = [], before = () => {} }: Serve = {}): void {
  ssmMock.on(GetParameterCommand).callsFake((input: GetParameterCommandInput) => {
    if (input.Name === MODEL_KEY_PARAM) return { Parameter: { Value: "test-model-key-0000000000000000000000" } };
    if (input.Name === "/lusot/spend/stop-usd") return { Parameter: { Value: "60" } };
    return { Parameter: { Value: stopped.some((name) => input.Name === `/lusot/stop/${name}`) ? "on" : "off" } };
  });
  ssmMock.on(PutParameterCommand).resolves({});
  // The spend counter, seeded and under its stop; any other item (a cached place, the Nominatim slot) is absent.
  ddbMock.on(GetCommand).callsFake((input: GetCommandInput) => {
    before();
    return input.Key?.pk === "spend#meta" ? { Item: { pk: "spend#meta", micro_usd: 3_000_000, seeded: true } } : {};
  });
  vi.stubGlobal("fetch", museSpark);
  ddbMock.on(QueryCommand).callsFake((input: QueryCommandInput) => {
    before();
    const values = input.ExpressionAttributeValues ?? {};
    if (":part" in values) return { Items: stored.filter((item) => item.feedPart === values[":part"]) };
    if (":pk" in values) return { Items: stored.filter((item) => item.pk === values[":pk"]) };
    return { Items: stored.filter((item) => item.reportId === values[":id"]) };
  });
  const written = () => {
    before();
    return {};
  };
  ddbMock.on(UpdateCommand).callsFake(written);
  ddbMock.on(PutCommand).callsFake(written);
  ddbMock.on(TransactWriteCommand).callsFake(written);
  s3Mock.on(GetObjectCommand).callsFake(() => {
    before();
    return { Body: objectBody(MANIFEST) };
  });
  s3Mock.on(CopyObjectCommand).callsFake(written);
}

const metaFixture = (name: string): { output: Record<string, unknown>[] } & Record<string, unknown> =>
  JSON.parse(readFileSync(new URL(`./fixtures/meta/${name}.json`, import.meta.url), "utf8"));

// Muse Spark as the OpenAI SDK reaches it, through fetch. Turn 1 calls get_reports: about "here" for a question
// with "dito", else about the question itself as the place; a question about "ulam" is off topic. The final turn
// cites r1 when the tool found live reports. Any other address fails: no test reaches the network.
async function museSpark(url: string | URL | Request, init?: RequestInit): Promise<Response> {
  if (!String(url).startsWith("https://api.meta.ai/v1/")) throw new Error(`no network in tests: ${String(url)}`);
  const body = JSON.parse(String(init?.body)) as { input: { type?: string; content?: { text: string }[]; output?: string }[] };
  const output = body.input.find((item) => item.type === "function_call_output")?.output;
  let reply: Record<string, unknown> & { output: Record<string, unknown>[] };
  if (output !== undefined) {
    reply = metaFixture("ask_answer");
    const cited = (JSON.parse(output) as { reports: unknown[] }).reports.length > 0 ? ["r1"] : [];
    (reply.output[1] as { content: { text: string }[] }).content[0].text = JSON.stringify({ kind: "depth", vehicle: "none", cited });
  } else {
    const question = body.input[0].content?.[1].text ?? "";
    if (question.includes("ulam")) {
      reply = metaFixture("ask_offtopic");
    } else {
      reply = metaFixture("ask_call");
      const here = /\bdito\b/i.test(question);
      reply.output[1].arguments = JSON.stringify({ place: here ? "" : question, here, since_minutes: 180, kind: "depth", vehicle: "none" });
    }
  }
  return new Response(JSON.stringify(reply), { status: 200, headers: { "content-type": "application/json" } });
}
