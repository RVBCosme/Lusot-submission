// S13: once every exact copy of the screen line is taken out, no copy pattern matches anything MS4's
// routes say, in any answer they can give (Important 15). Ask Lusot's POST /ask and POST /ask/voice join them (its
// Task 12).
import { ConditionalCheckFailedException, TransactionCanceledException } from "@aws-sdk/client-dynamodb";
import { CopyObjectCommand, GetObjectCommand } from "@aws-sdk/client-s3";
import { PutCommand, QueryCommand, TransactWriteCommand, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import type { APIGatewayProxyEventV2 } from "aws-lambda";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SCREEN_LINE } from "../src/copy";
import type { JsonResponse } from "../src/http";
import { awsError } from "./awsError";
import {
  ASK_HERE,
  coldHandler,
  DEMO_ID,
  DEMO_PIN,
  ddbMock,
  hearing,
  NOW,
  PIN,
  request,
  resetMocks,
  s3Mock,
  serve,
  stubApiEnv,
  UPLOAD,
  VOICE_AUDIO,
  wavBase64,
} from "./routeFixtures";

// Written out here, not imported, so a changed SCREEN_LINE fails the second test.
const LINE = "Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.";
const COPY_PATTERNS = [/safe/i, /ligtas/i, /\bcross/i, /tawid/i, /\b(roads?|streets?|routes?|kalsada|daan)\b/i];
// Data fields (a place is a street and city, spec §4.5, so it isn't MS4's wording; an answer's place.name and
// suggestions are spot or OpenStreetMap names, such as "Maginhawa Street", not Lusot's wording either; a spoken
// answer's transcript is the speaker's own words, which the app masks, AskL-Q11) and machine fields (presigned URLs
// and the signed form, whose signatures and base64 can match a pattern by chance).
const LEFT_OUT = new Set([
  "credit",
  "place",
  "event",
  "license",
  "suggestions",
  "transcript",
  "photoUrl",
  "overlayUrl",
  "layersUrl",
  "upload",
]);

// MS1's six details and MS4's two (uploads.ts).
const DETAILS = {
  "body must be JSON": "not json",
  "body must be a JSON object": "42",
  "lat must be a number from -90 to 90": JSON.stringify({ ...UPLOAD, lat: 91 }),
  "lng must be a number from -180 to 180": JSON.stringify({ ...UPLOAD, lng: 181 }),
  "gpsAccuracyM must be a number from 0 to 10000": JSON.stringify({ ...UPLOAD, gpsAccuracyM: -1 }),
  "nudgeM must be a number of at least 0": JSON.stringify({ ...UPLOAD, nudgeM: -1 }),
  "consentVersion must be 1 to 32 letters, digits, dots, dashes or underscores": JSON.stringify({ ...UPLOAD, consentVersion: "v 1" }),
  "capturedAt must be an ISO 8601 time with a time zone": JSON.stringify({ ...UPLOAD, capturedAt: "2026-10-30T10:05:12" }),
};

// Every reason a report ends with (pipeline/types.py's REFUSED_REASONS and FAILED_REASONS).
const REFUSED = ["too_dark", "too_blurry", "photo_unusable", "water_unsure", "no_water_found", "no_usable_reference", "references_disagree", "model_declined"];
const FAILED = ["model_calls_paused", "photo_missing", "bad_file", "model_error", "pipeline_error"];

let count = 0;
// A report at PIN's spot with its own id and the given state, as the upload and the analysis Lambda leave it.
function report(fields: Record<string, unknown>): Record<string, unknown> {
  const { pk, capturedAt, lat, lng, gpsAccuracyM, nudgeM, flags, visibleUntil, expiresAt } = PIN;
  const reportId = `r_${(0xa000 + count++).toString(16).padStart(32, "0")}`;
  return { pk, sk: `${capturedAt}#${reportId}`, reportId, mode: "live", capturedAt, lat, lng, gpsAccuracyM, nudgeM, flags, visibleUntil, expiresAt, ...fields };
}

const { feedPart: _feedPart, ...LEVEL } = PIN;
const REPORTS = [
  PIN,
  DEMO_PIN,
  // A level outside Metro Manila: analysed and shown, never pinned, so it has no feedPart (D14).
  { ...LEVEL, reportId: `r_${"b".repeat(32)}`, mode: "private", published: false },
  report({ status: "pending" }),
  report({ status: "processing", claimToken: "token-a", claimedAt: 1_793_354_725 }),
  report({ status: "done", noFloodSeen: true, published: false }),
  ...REFUSED.map((reason) => report({ status: "refused", refusalReason: reason })),
  ...FAILED.map((reason) => report({ status: "failed", refusalReason: reason })),
];

const refuseCount = (all: boolean) => () =>
  ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
    if (input.ConditionExpression !== undefined && String(input.Key?.pk).includes("#ALL#") === all) {
      throw new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });
    }
    return {};
  });
const denied = () => awsError("AccessDeniedException", 400);

interface Case {
  routeKey: string;
  fields?: Partial<APIGatewayProxyEventV2>;
  stopped?: string[];
  setup?: () => void;
}

const upload = (body: string): Case => ({ routeKey: "POST /uploads", fields: { body } });
const ask = (body: unknown): Case => ({ routeKey: "POST /ask", fields: { body: typeof body === "string" ? body : JSON.stringify(body) } });
const DITO = { question: "May baha ba dito?", here: ASK_HERE };
const voice = (body: unknown): Case => ({ routeKey: "POST /ask/voice", fields: { body: typeof body === "string" ? body : JSON.stringify(body) } });
const SPOKEN = { audio: VOICE_AUDIO, here: ASK_HERE };

// Ask's details (request.ts).
const ASK_DETAILS = {
  "body must be JSON": "not json",
  "body must be a JSON object": "42",
  "question must be a string": "{}",
  "question must be 1 to 300 characters": JSON.stringify({ question: " " }),
  "here must be an object": JSON.stringify({ question: "May baha ba?", here: "dito" }),
  "here.lat must be a number from -90 to 90": JSON.stringify({ ...DITO, here: { ...ASK_HERE, lat: 91 } }),
  "here.lng must be a number from -180 to 180": JSON.stringify({ ...DITO, here: { ...ASK_HERE, lng: 181 } }),
  "here.accuracyM must be a number from 0 to 100": JSON.stringify({ ...DITO, here: { ...ASK_HERE, accuracyM: 101 } }),
};

const CASES: Case[] = [
  upload(JSON.stringify(UPLOAD)),
  ...Object.values(DETAILS).map(upload),
  upload(JSON.stringify({ ...UPLOAD, capturedAt: "2026-10-30T09:50:00Z" })),
  upload(JSON.stringify({ ...UPLOAD, capturedAt: "2026-10-30T10:09:41Z" })),
  upload(JSON.stringify({ ...UPLOAD, gpsAccuracyM: 51 })),
  upload(JSON.stringify({ ...UPLOAD, nudgeM: 101 })),
  { ...upload(JSON.stringify(UPLOAD)), setup: refuseCount(false) },
  { ...upload(JSON.stringify(UPLOAD)), setup: refuseCount(true) },
  { ...upload(JSON.stringify(UPLOAD)), stopped: ["uploads"] },
  { ...upload(JSON.stringify(UPLOAD)), setup: () => ddbMock.on(PutCommand).rejects(denied()) },

  ...REPORTS.map((item): Case => ({ routeKey: "GET /reports/{id}", fields: { pathParameters: { id: item.reportId as string } } })),
  { routeKey: "GET /reports/{id}", fields: { pathParameters: { id: `r_${"c".repeat(32)}` } } },
  { routeKey: "GET /reports/{id}", fields: { pathParameters: { id: "not-an-id" } } },
  { routeKey: "GET /reports/{id}", setup: () => ddbMock.on(QueryCommand).rejects(denied()) },

  { routeKey: "GET /reports" },
  { routeKey: "GET /reports", stopped: ["publish"] },
  { routeKey: "GET /reports", fields: { queryStringParameters: { lng: "120.9894" } } },
  { routeKey: "GET /reports", fields: { queryStringParameters: { lat: "14.6095", lng: "120.9894", radius: "301" } } },
  { routeKey: "GET /reports", setup: () => ddbMock.on(QueryCommand).rejects(denied()) },

  { routeKey: "GET /map/pins" },
  { routeKey: "GET /map/pins", setup: () => ddbMock.on(QueryCommand).rejects(denied()) },

  { routeKey: "GET /pins.geojson" },
  { routeKey: "GET /pins.geojson", setup: () => ddbMock.on(QueryCommand).rejects(denied()) },

  { routeKey: "POST /reports/{id}/flag" },
  {
    routeKey: "POST /reports/{id}/flag",
    setup: () =>
      ddbMock.on(TransactWriteCommand).rejects(
        new TransactionCanceledException({
          message: "Transaction cancelled",
          $metadata: { httpStatusCode: 400 },
          CancellationReasons: [{ Code: "ConditionalCheckFailed" }, { Code: "None" }],
        }),
      ),
  },
  { routeKey: "POST /reports/{id}/flag", fields: { pathParameters: { id: DEMO_ID } } },
  { routeKey: "POST /reports/{id}/flag", setup: () => ddbMock.on(TransactWriteCommand).rejects(denied()) },

  { routeKey: "GET /samples" },
  { routeKey: "GET /samples", setup: () => s3Mock.on(GetObjectCommand).rejects(denied()) },

  { routeKey: "POST /samples/{sampleId}" },
  { routeKey: "POST /samples/{sampleId}", stopped: ["model-calls"] },
  { routeKey: "POST /samples/{sampleId}", fields: { pathParameters: { sampleId: "s9999999999" } } },
  { routeKey: "POST /samples/{sampleId}", setup: refuseCount(false) },
  { routeKey: "POST /samples/{sampleId}", setup: refuseCount(true) },
  { routeKey: "POST /samples/{sampleId}", stopped: ["uploads"] },
  { routeKey: "POST /samples/{sampleId}", setup: () => s3Mock.on(CopyObjectCommand).rejects(denied()) },

  ask(DITO),
  { ...ask(DITO), stopped: ["model-calls"] },
  ask({ ...DITO, here: { lat: 14.61443, lng: 120.99802, accuracyM: 20 } }), // in Metro Manila, with no pin near
  ask({ ...DITO, here: { lat: 14.2, lng: 121.1, accuracyM: 20 } }), // outside Metro Manila
  ask({ question: "May baha ba dito?" }),
  ask({ question: "Taft Avenue" }), // a road with several listed spots
  { ...ask({ question: "Maginhawa Street" }), stopped: ["nominatim"] },
  ask({ question: "Ano ang ulam mamaya?" }),
  { ...ask({ question: "May baha ba?" }), stopped: ["model-calls"] },
  ...Object.values(ASK_DETAILS).map(ask),
  { ...ask(DITO), setup: refuseCount(false) },
  { ...ask(DITO), setup: refuseCount(true) },
  { ...ask(DITO), setup: () => ddbMock.on(QueryCommand).rejects(denied()) },
  { ...ask(DITO), setup: () => ddbMock.on(UpdateCommand).rejects(denied()) },

  voice(SPOKEN),
  { ...voice(SPOKEN), stopped: ["model-calls"] },
  { ...voice(SPOKEN), setup: () => hearing("") },
  { ...voice(SPOKEN), setup: () => hearing(503) },
  voice("not json"),
  voice("42"),
  voice({ ...SPOKEN, here: "dito" }),
  voice({ audio: "not base64!" }),
  voice({ audio: wavBase64(0.2) }),
  voice({ audio: wavBase64(15.5) }),
  { ...voice(SPOKEN), setup: refuseCount(false) },
  { ...voice(SPOKEN), setup: refuseCount(true) },
  { ...voice(SPOKEN), setup: () => ddbMock.on(QueryCommand).rejects(denied()) },
  { ...voice(SPOKEN), setup: () => ddbMock.on(UpdateCommand).rejects(denied()) },

  { routeKey: "GET /nope" },
];

// Every (route, status, code) answer the routes can give.
const ANSWERS = [
  "POST /uploads 201",
  ...Object.keys(DETAILS).map((detail) => `POST /uploads 400 bad_request: ${detail}`),
  "POST /uploads 422 capture_too_old",
  "POST /uploads 422 capture_in_future",
  "POST /uploads 422 gps_too_coarse",
  "POST /uploads 422 nudge_too_far",
  "POST /uploads 429 device_limit",
  "POST /uploads 429 global_cap",
  "POST /uploads 503 uploads_paused",
  "POST /uploads 500 internal",
  "GET /reports/{id} 200",
  "GET /reports/{id} 404 not_found",
  "GET /reports/{id} 500 internal",
  "GET /reports 200",
  "GET /reports 400 bad_point",
  "GET /reports 400 bad_radius",
  "GET /reports 500 internal",
  "GET /map/pins 200",
  "GET /map/pins 500 internal",
  "GET /pins.geojson 200",
  "GET /pins.geojson 500 internal",
  "POST /reports/{id}/flag 200",
  "POST /reports/{id}/flag 404 not_found",
  "POST /reports/{id}/flag 500 internal",
  "GET /samples 200",
  "GET /samples 500 internal",
  "POST /samples/{sampleId} 201",
  "POST /samples/{sampleId} 200 saved",
  "POST /samples/{sampleId} 404 not_found",
  "POST /samples/{sampleId} 429 device_limit",
  "POST /samples/{sampleId} 429 global_cap",
  "POST /samples/{sampleId} 503 uploads_paused",
  "POST /samples/{sampleId} 500 internal",
  "POST /ask 200 model reports",
  "POST /ask 200 plain_list reports",
  "POST /ask 200 model no_reports",
  "POST /ask 200 model outside_metro_manila",
  "POST /ask 200 model no_location",
  "POST /ask 200 model place_too_broad",
  "POST /ask 200 model lookup_unavailable",
  "POST /ask 200 model off_topic",
  "POST /ask 200 plain_list no_place",
  ...Object.keys(ASK_DETAILS).map((detail) => `POST /ask 400 bad_request: ${detail}`),
  "POST /ask 429 question_limit",
  "POST /ask 429 question_cap",
  "POST /ask 503 ask_unavailable",
  "POST /ask 500 internal",
  "POST /ask/voice 200 model reports",
  "POST /ask/voice 200 model no_speech",
  "POST /ask/voice 400 bad_request: body must be JSON",
  "POST /ask/voice 400 bad_request: body must be a JSON object",
  "POST /ask/voice 400 bad_request: here must be an object",
  "POST /ask/voice 400 bad_audio",
  "POST /ask/voice 422 audio_too_short",
  "POST /ask/voice 422 audio_too_long",
  "POST /ask/voice 429 question_limit",
  "POST /ask/voice 429 question_cap",
  "POST /ask/voice 503 voice_paused",
  "POST /ask/voice 503 voice_failed",
  "POST /ask/voice 503 ask_unavailable",
  "POST /ask/voice 500 internal",
  "GET /nope 404 not_found",
];

function answer(routeKey: string, res: JsonResponse): string {
  const body = JSON.parse(res.body);
  let code = "";
  if (typeof body.error === "string") code = body.detail === undefined ? body.error : `${body.error}: ${body.detail}`;
  else if (body.saved === true) code = "saved";
  else if (body.answer !== undefined) code = `${body.answer.source} ${body.answer.kind}`;
  return `${routeKey} ${res.statusCode} ${code}`.trim();
}

// Every value in the body, by key, but the fields left out.
function values(value: unknown, out: string[]): void {
  if (Array.isArray(value)) for (const entry of value) values(entry, out);
  else if (value !== null && typeof value === "object") {
    for (const [key, entry] of Object.entries(value)) if (!LEFT_OUT.has(key)) values(entry, out);
  } else if (value !== undefined && value !== null) out.push(String(value));
}

beforeEach(() => {
  stubApiEnv();
  vi.setSystemTime(Date.parse(NOW));
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "log").mockImplementation(() => {}); // Ask's log line and its spend line
});

afterEach(() => {
  resetMocks();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("copy", () => {
  // Its own timeout: every case imports a cold handler, so the module caches (switches, the key, the clients) never
  // carry over, and the whole run takes about 4 s alone, close to vitest's 5 s default on a loaded machine.
  it("keeps every route's bodies free of the banned words, crossing advice and whole-road wording", { timeout: 30_000 }, async () => {
    const seen = new Set<string>();
    const said: string[] = [];
    for (const { routeKey, fields, stopped, setup } of CASES) {
      resetMocks();
      serve({ stored: REPORTS, stopped });
      setup?.();
      const res = await (await coldHandler())(request(routeKey, fields));
      seen.add(answer(routeKey, res));
      said.push(...Object.values(res.headers));
      values(JSON.parse(res.body), said);
    }

    // The fixtures gave every answer, and only those, so the check below can't pass on an empty join (T7).
    expect([...seen].sort()).toEqual([...ANSWERS].sort());
    // Codes are snake_case, and \b doesn't break at "_", so they are read as words.
    const text = said.join("\n").replaceAll(SCREEN_LINE, "").replaceAll("_", " ");
    expect(text).toContain("rim three quarters");
    for (const pattern of COPY_PATTERNS) expect(text.match(pattern), String(pattern)).toBeNull();
  });

  it("carries the screen line word for word as the feed's notice", async () => {
    serve();

    const res = await (await coldHandler())(request("GET /pins.geojson"));

    expect(res.statusCode).toBe(200);
    expect(JSON.parse(res.body).notice).toBe(LINE);
  });
});
