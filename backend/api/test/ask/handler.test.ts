// POST /ask (typed only, Oct 30): the handler in spec §4.1's order, over class-free fakes. A fake Meta replays the
// fixtures in test/fixtures/meta/ (Task 2's shapes), a manual clock stands for the time, and the two DynamoDB
// clients and SSM are aws-sdk-client-mock instance mocks. No network, no AWS, no key.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { format } from "node:util";
import { ConditionalCheckFailedException, DynamoDBClient, type DynamoDBClientConfig } from "@aws-sdk/client-dynamodb";
import { GetParameterCommand, PutParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, GetCommand, UpdateCommand, type UpdateCommandInput } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import type { Response } from "openai/resources/responses/responses";
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import { type AskDeps, askTyped, NCR_BOUNDS, SPEND_CLIENT_CONFIG, SPEND_STOP_PARAM } from "../../src/ask/handler";
import { BUDGET } from "../../src/ask/deadline";
import { ASK_LOG_FIELDS } from "../../src/ask/log";
import { type Meta, type MetaCall, type MetaDeps, MetaError } from "../../src/ask/meta";
import type { Geocoder } from "../../src/ask/nominatim";
import { parseQuestion } from "../../src/ask/request";
import { SPOTS } from "../../src/ask/spots";
import ncr from "../../src/data/ncr.json";
import type { JsonResponse } from "../../src/http";
import { retryAfterS } from "../../src/limits";
import { inMetroManila } from "../../src/metroManila";
import type { ModelKey } from "../../src/modelKey";
import type { PublicPin } from "../../src/pins";
import { createStopSwitch } from "../../src/stopSwitch";
import { awsError } from "../awsError";

const START = Date.parse("2026-10-30T10:06:40Z");
const START_S = START / 1000;
const DEVICE = "device-0123456789abcdef";
const KEY = "test-model-key-0000000000000000000000";
const QUESTION = "Gaano kalalim ang baha sa España cor. Maceda?";
const ESPANA = SPOTS.find((spot) => spot.id === "espana-maceda");
if (ESPANA === undefined) throw new Error("the spot list has no España cor. Maceda");
const HERE = { lat: 14.6095, lng: 120.9894, accuracyM: 20 };
// Not on the spot list, so a call for it goes to the geocoder.
const UNLISTED = "Maginhawa Street";

// --- the Meta replies ------------------------------------------------------------------------------------------

type Fixture = Record<string, unknown> & { output: Record<string, unknown>[] };
const fixture = (name: string): Fixture =>
  JSON.parse(readFileSync(new URL(`../fixtures/meta/${name}.json`, import.meta.url), "utf8"));

const CALL_ARGS = { place: "España cor. Maceda", here: false, since_minutes: 180, kind: "depth", vehicle: "none" };

function callReply(args: Record<string, unknown> | string = {}): Fixture {
  const reply = fixture("ask_call");
  reply.output[1].arguments = typeof args === "string" ? args : JSON.stringify({ ...CALL_ARGS, ...args });
  return reply;
}

function verdictReply(verdict: Record<string, unknown> = {}): Fixture {
  const reply = fixture("ask_answer");
  (reply.output[1] as { content: { text: string }[] }).content[0].text = JSON.stringify({
    kind: "depth",
    vehicle: "none",
    cited: ["r1", "r2"],
    ...verdict,
  });
  return reply;
}

// --- the fakes -------------------------------------------------------------------------------------------------

let clock: number;

type Step = { reply: Fixture | Error; takes?: number; tries?: (number | null)[] };
const step = (reply: Fixture | Error, over: Omit<Step, "reply"> = {}): Step => ({ reply, ...over });

// One Meta per question, as the handler's factory makes it. A MetaError is thrown with its status; any other
// error is thrown after a 200, as an answer the SDK couldn't read would be.
function fakeMeta(steps: Step[]): { meta: Meta; bodies: Record<string, unknown>[] } {
  const calls: MetaCall[] = [];
  const bodies: Record<string, unknown>[] = [];
  const meta: Meta = {
    calls,
    async respond(body) {
      bodies.push(JSON.parse(JSON.stringify(body)));
      const next = steps.shift();
      if (next === undefined) throw new Error("the test scripted no reply for this call");
      for (const status of next.tries ?? []) calls.push({ model: "muse-spark-1.3", status, ms: 0 });
      clock += next.takes ?? 0;
      calls.push({ model: "muse-spark-1.3", status: next.reply instanceof MetaError ? next.reply.status : 200, ms: 0 });
      if (next.reply instanceof Error) throw next.reply;
      return next.reply as unknown as Response;
    },
  };
  return { meta, bodies };
}

let counter: number;
function pin(fields: Partial<PublicPin> = {}, minutesAgo = 10): PublicPin {
  return {
    id: `r_${(0xa000 + counter++).toString(16).padStart(32, "0")}`,
    lat: ESPANA?.lat ?? 0,
    lng: ESPANA?.lng ?? 0,
    gpsAccuracyM: 12,
    capturedAt: new Date(START - minutesAgo * 60_000).toISOString(),
    mode: "live",
    level: "knee",
    landmark: "rim_three_quarters",
    passability: "NPLV",
    levelIsFloor: false,
    basis: { vehicles: 1, people: 0 },
    flags: 0,
    ...fields,
  };
}

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const spendDdb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ssm = new SSMClient({ region: "ap-southeast-1" });
const ddbMock = mockClient(ddb);
const spendMock = mockClient(spendDdb);
const ssmMock = mockClient(ssm);

type World = {
  stopped: Set<string>;
  steps: Step[];
  bodies: Record<string, unknown>[];
  pins: PublicPin[];
  nearbyPins: Mock<AskDeps["nearbyPins"]>;
  geocode: Mock<Geocoder["geocode"]>;
  modelKey: { get: Mock<ModelKey["get"]>; drop: Mock<ModelKey["drop"]> };
  createMeta: Mock<AskDeps["createMeta"]>;
  lines: string[];
};
let w: World;

function deps(over: Partial<AskDeps> = {}): AskDeps {
  return {
    ddb,
    limitsTableName: "limits",
    isStopped: async (name) => w.stopped.has(name),
    nearbyPins: w.nearbyPins,
    inMetroManila,
    spots: SPOTS,
    geocoder: { geocode: w.geocode },
    modelKey: w.modelKey,
    createMeta: w.createMeta,
    spendDdb,
    ssm,
    stopParamPrefix: "/lusot/stop/",
    now: () => clock,
    sleep: async (ms) => {
      clock += ms;
    },
    random: () => 0.5,
    ...over,
  };
}

const ask = (body: unknown, over: Partial<AskDeps> = {}, device: string | undefined = DEVICE): Promise<JsonResponse> =>
  askTyped({ body: typeof body === "string" || body === undefined ? body : JSON.stringify(body), device }, deps(over));

const parsed = (res: JsonResponse) => JSON.parse(res.body);
const askLines = () => w.lines.filter((line) => line.startsWith("{") && JSON.parse(line).msg === "ask").map((line) => JSON.parse(line));
const lastAskLine = () => askLines().at(-1);
const linesWith = (msg: string) => w.lines.filter((line) => line.includes(`"msg":"${msg}"`)).map((line) => JSON.parse(line));
const counterKeys = () => ddbMock.commandCalls(UpdateCommand).map((call) => String(call.args[0].input.Key?.pk));
const spendWrites = () => spendMock.commandCalls(UpdateCommand).map((call) => call.args[0].input);
const pauses = () =>
  ssmMock.commandCalls(PutParameterCommand).map(({ args: [{ input }] }) => ({ name: input.Name, value: input.Value, overwrite: input.Overwrite }));

beforeEach(() => {
  clock = START;
  counter = 0;
  ddbMock.reset();
  spendMock.reset();
  ssmMock.reset();
  ddbMock.on(UpdateCommand).resolves({});
  spendMock.on(GetCommand).resolves({ Item: { pk: "spend#meta", micro_usd: 3_000_000, seeded: true } });
  spendMock.on(UpdateCommand).resolves({ Attributes: { micro_usd: 3_007_229 } });
  ssmMock.on(GetParameterCommand, { Name: SPEND_STOP_PARAM }).resolves({ Parameter: { Value: "60" } });
  ssmMock.on(PutParameterCommand).resolves({});

  // Two live reports at the spot, the knee one deepest, and a demo pin.
  const pins = [
    pin({ level: "knee" }, 10),
    pin({ level: "half_tire" }, 30),
    pin({ mode: "demo", capturedAt: "2009-09-26T02:30:00Z", credit: "Photo by a donor", place: "Rizal Avenue, Manila" }),
  ];
  const steps = [step(callReply()), step(verdictReply())];
  const lines: string[] = [];
  for (const method of ["log", "info", "warn", "error", "debug"] as const) {
    vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
      lines.push(format(...args));
    });
  }
  w = {
    stopped: new Set(),
    steps,
    bodies: [],
    pins,
    nearbyPins: vi.fn<AskDeps["nearbyPins"]>(async () => w.pins),
    geocode: vi.fn<Geocoder["geocode"]>(async () => ({ trace: "off" as const })),
    modelKey: { get: vi.fn<ModelKey["get"]>(async () => KEY), drop: vi.fn<ModelKey["drop"]>() },
    createMeta: vi.fn<AskDeps["createMeta"]>(() => {
      const fake = fakeMeta(w.steps);
      w.bodies = fake.bodies;
      return fake.meta;
    }),
    lines,
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

const conditionFailed = () => new ConditionalCheckFailedException({ message: "The conditional request failed", $metadata: {} });

// Nothing was counted, nothing paid, nothing looked up.
function expectUntouched(): void {
  expect(ddbMock.calls()).toHaveLength(0);
  expect(spendMock.calls()).toHaveLength(0);
  expect(ssmMock.calls()).toHaveLength(0);
  expect(w.createMeta).not.toHaveBeenCalled();
  expect(w.modelKey.get).not.toHaveBeenCalled();
  expect(w.geocode).not.toHaveBeenCalled();
  expect(w.nearbyPins).not.toHaveBeenCalled();
}

// --- the tests -------------------------------------------------------------------------------------------------

describe("requests (spec §5.1, §5.4)", () => {
  it.each([
    ["no body", undefined, "body must be JSON"],
    ["malformed JSON", "{not json", "body must be JSON"],
    ["a number", "42", "body must be a JSON object"],
    ["a list", "[]", "body must be a JSON object"],
    ["no question", {}, "question must be a string"],
    ["a question that isn't text", { question: 7 }, "question must be a string"],
    ["an empty question", { question: "" }, "question must be 1 to 300 characters"],
    ["a question of spaces only", { question: "   \n " }, "question must be 1 to 300 characters"],
    ["a question of 301 characters", { question: "a".repeat(301) }, "question must be 1 to 300 characters"],
    ["here that isn't an object", { question: QUESTION, here: "dito" }, "here must be an object"],
    ["here as null", { question: QUESTION, here: null }, "here must be an object"],
    ["here without lat", { question: QUESTION, here: { lng: 120.9894, accuracyM: 20 } }, "here.lat must be a number from -90 to 90"],
    ["here with lat 91", { question: QUESTION, here: { ...HERE, lat: 91 } }, "here.lat must be a number from -90 to 90"],
    ["here with lng -181", { question: QUESTION, here: { ...HERE, lng: -181 } }, "here.lng must be a number from -180 to 180"],
    ["here with a text lng", { question: QUESTION, here: { ...HERE, lng: "120.9894" } }, "here.lng must be a number from -180 to 180"],
    ["here with accuracyM 101", { question: QUESTION, here: { ...HERE, accuracyM: 101 } }, "here.accuracyM must be a number from 0 to 100"],
    ["here with accuracyM -1", { question: QUESTION, here: { ...HERE, accuracyM: -1 } }, "here.accuracyM must be a number from 0 to 100"],
  ])("%s gives 400 bad_request, with no count, no Meta call and no Nominatim call", async (_name, body, detail) => {
    const res = await ask(body);

    expect(res.statusCode).toBe(400);
    expect(parsed(res)).toEqual({ error: "bad_request", detail });
    expectUntouched();
    expect(lastAskLine()).toMatchObject({ route: "ask", status: 400, code: "bad_request" });
  });

  it("trims the question and counts characters, not UTF-16 units", () => {
    expect(parseQuestion(JSON.stringify({ question: `  ${QUESTION}\n` }))).toEqual({ question: QUESTION });
    expect(parseQuestion(JSON.stringify({ question: "a".repeat(300) }))).toEqual({ question: "a".repeat(300) });
    // 300 emoji are 600 UTF-16 units, and still 300 characters.
    expect(parseQuestion(JSON.stringify({ question: "🌧".repeat(300) }))).toEqual({ question: "🌧".repeat(300) });
    expect(parseQuestion(JSON.stringify({ question: "🌧".repeat(301) }))).toEqual({ detail: "question must be 1 to 300 characters" });
  });

  it("keeps here's three fields only, at their edges", () => {
    const edge = { lat: -90, lng: 180, accuracyM: 100, extra: "dropped" };
    expect(parseQuestion(JSON.stringify({ question: "dito", here: edge }))).toEqual({
      question: "dito",
      here: { lat: -90, lng: 180, accuracyM: 100 },
    });
    expect(parseQuestion(JSON.stringify({ question: "dito", here: { ...HERE, accuracyM: 0 } }))).toEqual({ question: "dito", here: { ...HERE, accuracyM: 0 } });
  });
});

describe("the caps (spec §4.8)", () => {
  it("a refused device gives 429 question_limit with Retry-After, and leaves the hour's counter untouched", async () => {
    ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
      if (!String(input.Key?.pk).includes("#ALL#")) throw conditionFailed();
      return {};
    });

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(429);
    expect(parsed(res)).toEqual({ error: "question_limit" });
    expect(res.headers["retry-after"]).toBe(String(retryAfterS(START_S)));
    const hash = createHash("sha256").update(DEVICE).digest("hex");
    expect(counterKeys()).toEqual([`question#${hash}#2026-10-30T10`]);
    expect(w.createMeta).not.toHaveBeenCalled();
    expect(spendMock.calls()).toHaveLength(0);
    expect(lastAskLine()).toMatchObject({ status: 429, code: "question_limit" });
  });

  it("a full hour gives 429 question_cap with Retry-After, and gives the device's count back", async () => {
    ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
      if (String(input.Key?.pk).includes("#ALL#")) throw conditionFailed();
      return {};
    });

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(429);
    expect(parsed(res)).toEqual({ error: "question_cap" });
    expect(res.headers["retry-after"]).toBe(String(retryAfterS(START_S)));
    const hash = createHash("sha256").update(DEVICE).digest("hex");
    expect(counterKeys()).toEqual([`question#${hash}#2026-10-30T10`, "question#ALL#2026-10-30T10", `question#${hash}#2026-10-30T10`]);
    expect(w.createMeta).not.toHaveBeenCalled();
    expect(w.nearbyPins).not.toHaveBeenCalled();
    expect(lastAskLine()).toMatchObject({ status: 429, code: "question_cap" });
  });

  it("counts a question once, the device first, before any Meta call", async () => {
    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(200);
    const hash = createHash("sha256").update(DEVICE).digest("hex");
    expect(counterKeys()).toEqual([`question#${hash}#2026-10-30T10`, "question#ALL#2026-10-30T10"]);
  });
});

describe("the model-calls switch (spec §4.8)", () => {
  it("on: a typed question gives the plain list, with no Meta call and meta_calls 0", async () => {
    w.stopped.add("model-calls");

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(200);
    expect(parsed(res).answer).toMatchObject({ source: "plain_list", fallback: "model_calls_paused", kind: "reports", vehicle: null, cited: [] });
    expect(w.createMeta).not.toHaveBeenCalled();
    expect(w.modelKey.get).not.toHaveBeenCalled();
    expect(spendMock.calls()).toHaveLength(0);
    expect(counterKeys()).toHaveLength(2); // still counted (spec §4.8)
    expect(lastAskLine()).toMatchObject({ source: "plain_list", fallback: "model_calls_paused", meta_calls: 0, tool_calls: 0, final: null });
  });

  it("unreadable counts as on", async () => {
    ssmMock.on(GetParameterCommand).rejects(awsError("AccessDeniedException", 400));

    const res = await ask({ question: QUESTION }, { isStopped: createStopSwitch(ssm, "/lusot/stop/") });

    expect(parsed(res).answer).toMatchObject({ source: "plain_list", fallback: "model_calls_paused" });
    expect(w.createMeta).not.toHaveBeenCalled();
  });
});

describe("the plain list's own place (spec §4.5)", () => {
  beforeEach(() => {
    w.stopped.add("model-calls");
  });

  it("finds a listed spot named in the question, with no Nominatim call", async () => {
    const res = await ask({ question: "Baha ba sa España cor. Maceda?" });

    expect(parsed(res).answer).toMatchObject({ kind: "reports", place: { name: ESPANA.name, source: "spots" }, windowMin: 180, count: 2 });
    expect(w.nearbyPins).toHaveBeenCalledWith(ESPANA.lat, ESPANA.lng, 300);
    expect(w.geocode).not.toHaveBeenCalled();
    expect(lastAskLine()).toMatchObject({ place_source: "spots", nominatim: null, reports: 2, demo: 1, cited: 0 });
  });

  it("uses the location sent when the question names no spot", async () => {
    const res = await ask({ question: "May baha ba?", here: HERE });

    expect(parsed(res).answer.place).toEqual({ name: "here", source: "here" });
    expect(w.nearbyPins).toHaveBeenCalledWith(HERE.lat, HERE.lng, 300);
  });

  it("a here word with a location sent takes the location over a named spot", async () => {
    const res = await ask({ question: "Baha ba dito sa España cor. Maceda?", here: HERE });

    expect(parsed(res).answer.place).toEqual({ name: "here", source: "here" });
    expect(w.nearbyPins).toHaveBeenCalledWith(HERE.lat, HERE.lng, 300);
  });

  it("a here word without a location gives no_location, even beside a named spot", async () => {
    // Spec §4.5, literally (the controller's ruling): a "here" word means the phone's location, as the model's
    // `here: true` call would.
    const spot = await ask({ question: "Baha ba dito sa España cor. Maceda?" });
    expect(parsed(spot).answer).toMatchObject({ kind: "no_location", place: null });

    const none = await ask({ question: "May baha ba dito?" });
    expect(parsed(none).answer).toMatchObject({ kind: "no_location", place: null });
    expect(w.nearbyPins).not.toHaveBeenCalled();
  });

  it("neither a spot nor a location gives no_place, with no pins read", async () => {
    const res = await ask({ question: "May baha ba?" });

    expect(parsed(res).answer).toMatchObject({ source: "plain_list", kind: "no_place", place: null, reports: [], demo: [] });
    expect(w.nearbyPins).not.toHaveBeenCalled();
    expect(w.geocode).not.toHaveBeenCalled();
  });

  it("a road alone isn't a place: it gives no_place, never a road's spots", async () => {
    const res = await ask({ question: "May baha ba sa Taft Avenue?" });

    expect(parsed(res).answer.kind).toBe("no_place");
  });

  it("takes the crossing line from the question's words only", async () => {
    const res = await ask({ question: "Kaya bang tumawid sa España cor. Maceda?" });

    expect(parsed(res).answer).toMatchObject({ crossing: true, vehicle: null });
    expect(lastAskLine()).toMatchObject({ crossing: "words" });
  });

  it("a turn-1 fallback answers the same way, with its own code", async () => {
    w.stopped.clear();
    w.steps.splice(0, w.steps.length, step(callReply("{not json")));

    const res = await ask({ question: "Baha ba sa España cor. Maceda?" });

    expect(parsed(res).answer).toMatchObject({ source: "plain_list", fallback: "invalid_answer", kind: "reports", place: { source: "spots" } });
    expect(w.geocode).not.toHaveBeenCalled();
    expect(lastAskLine()).toMatchObject({ fallback: "invalid_answer", meta_calls: 1, final: null, tool_calls: 0 });
  });
});

describe("the model's answer", () => {
  it("one call, one tool run, an answer with citations, and its log line", async () => {
    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(200);
    const { answer } = parsed(res);
    expect(answer).toMatchObject({
      source: "model",
      fallback: null,
      kind: "reports",
      crossing: false,
      vehicle: null,
      place: { name: ESPANA.name, source: "spots" },
      count: 2,
      deepestId: w.pins[0].id,
      cited: [w.pins[0].id, w.pins[1].id],
    });
    expect(Object.keys(parsed(res))).toEqual(["answer"]);
    expect(lastAskLine()).toEqual({
      msg: "ask",
      route: "ask",
      status: 200,
      source: "model",
      fallback: null,
      kind: "reports",
      crossing: null,
      vehicle: null,
      place_source: "spots",
      nominatim: null,
      reports: 2,
      demo: 1,
      cited: 2,
      tool_calls: 1,
      final: "ok",
      meta_calls: 2,
      input_tokens: 1285 + 1897,
      output_tokens: 445 + 320,
      reasoning_tokens: 307 + 287,
      model_ms: 0,
      ms: 0,
    });
  });

  it("makes one Meta per question with the key, and reads the key inside the model mark", async () => {
    await ask({ question: QUESTION });
    await ask({ question: QUESTION });

    expect(w.createMeta).toHaveBeenCalledTimes(2);
    const metaDeps = w.createMeta.mock.calls[0][0] as MetaDeps;
    expect(metaDeps.key).toBe(KEY);
    expect(metaDeps.fetchFn).toBeUndefined();
    expect(w.modelKey.get.mock.calls[0][0]).toBeInstanceOf(AbortSignal);
  });

  it("logs the Nominatim trace and its place source", async () => {
    w.geocode.mockResolvedValue({
      result: { status: "found", name: "Jollibee Maginhawa", lat: 14.6501, lng: 121.0501, box: { south: 14.65, north: 14.6502, west: 121.05, east: 121.0502 }, spanM: 30 },
      trace: "called",
    });
    w.steps.splice(0, w.steps.length, step(callReply({ place: "Jollibee Maginhawa" })), step(verdictReply()));

    const res = await ask({ question: "Baha ba sa Jollibee Maginhawa?" });

    expect(parsed(res).answer.place).toEqual({ name: "Jollibee Maginhawa", source: "nominatim" });
    expect(lastAskLine()).toMatchObject({ place_source: "nominatim", nominatim: "called" });
  });

  it("a crossing question on both counts logs both, and a light vehicle stays light", async () => {
    w.steps.splice(0, w.steps.length, step(callReply({ kind: "crossing", vehicle: "light" })), step(verdictReply({ kind: "crossing", vehicle: "light" })));

    const res = await ask({ question: "Kaya bang tumawid ng kotse sa España cor. Maceda?" });

    expect(parsed(res).answer).toMatchObject({ crossing: true, vehicle: "light" });
    expect(lastAskLine()).toMatchObject({ crossing: "both", vehicle: "light" });
  });

  it("a rejected key gives the plain list (key_rejected), drops the key and logs meta_status", async () => {
    w.steps.splice(0, w.steps.length, step(new MetaError(402)));

    const res = await ask({ question: QUESTION });

    expect(parsed(res).answer).toMatchObject({ source: "plain_list", fallback: "key_rejected", kind: "reports" });
    expect(w.modelKey.drop).toHaveBeenCalledTimes(1);
    expect(lastAskLine()).toMatchObject({ fallback: "key_rejected", meta_calls: 1, meta_status: 402 });
    expect(spendWrites()).toHaveLength(0); // an HTTP error isn't billed
  });

  it("the deadline in turn 1 gives the plain list, with meta_status null", async () => {
    w.steps.splice(0, w.steps.length, step(new MetaError(null), { takes: 7600 }));

    const res = await ask({ question: QUESTION });

    expect(parsed(res).answer).toMatchObject({ source: "plain_list", fallback: "deadline" });
    expect(lastAskLine()).toMatchObject({ fallback: "deadline", meta_calls: 1, meta_status: null, model_ms: 7600 });
  });

  it("a retry that then succeeds leaves meta_status out", async () => {
    w.steps.splice(0, w.steps.length, step(callReply(), { tries: [503] }), step(verdictReply()));

    await ask({ question: QUESTION });

    expect(lastAskLine()).toMatchObject({ meta_calls: 3, final: "ok" });
    expect(lastAskLine()).not.toHaveProperty("meta_status");
  });

  it("a final turn that fails keeps the answer and logs the failing status", async () => {
    w.steps.splice(0, w.steps.length, step(callReply()), step(new MetaError(500)));

    const res = await ask({ question: QUESTION });

    expect(parsed(res).answer).toMatchObject({ source: "model", kind: "reports", cited: [] });
    expect(lastAskLine()).toMatchObject({ final: "failed", meta_status: 500, meta_calls: 2 });
  });

  it("an off-topic question logs final null and no tool call", async () => {
    w.steps.splice(0, w.steps.length, step(fixture("ask_offtopic")));

    const res = await ask({ question: "Ano ang ulam mamaya?" });

    expect(parsed(res).answer).toMatchObject({ source: "model", kind: "off_topic", place: null });
    expect(lastAskLine()).toMatchObject({ kind: "off_topic", final: null, tool_calls: 0, meta_calls: 1 });
  });

  it("a key that can't be read gives the plain list (model_error), with no Meta made", async () => {
    w.modelKey.get.mockRejectedValue(awsError("ParameterNotFound", 400));

    const res = await ask({ question: QUESTION });

    expect(parsed(res).answer).toMatchObject({ source: "plain_list", fallback: "model_error" });
    expect(w.createMeta).not.toHaveBeenCalled();
    expect(lastAskLine()).toMatchObject({ fallback: "model_error", meta_calls: 0 });
    expect(linesWith("model_key_unreadable")).toEqual([{ msg: "model_key_unreadable", error: "ParameterNotFound", status: 400 }]);
  });
});

describe("the pins read (spec §5.4)", () => {
  it("a read that fails in the tool gives 503 ask_unavailable, and the paid turn is recorded", async () => {
    w.nearbyPins.mockRejectedValue(awsError("ProvisionedThroughputExceededException", 400));

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(503);
    expect(parsed(res)).toEqual({ error: "ask_unavailable" });
    // ask_call.json: 1285 in, 445 out: $0.0034975, rounded up to 3,498 micro-dollars.
    expect(spendWrites().map((input) => input.ExpressionAttributeValues?.[":n"])).toEqual([3498]);
    expect(lastAskLine()).toMatchObject({ status: 503, code: "ask_unavailable", tool_calls: 1, meta_calls: 1, input_tokens: 1285 });
  });

  it("a read that fails for the plain list gives 503 ask_unavailable", async () => {
    w.stopped.add("model-calls");
    w.nearbyPins.mockRejectedValue(awsError("ProvisionedThroughputExceededException", 400));

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(503);
    expect(parsed(res)).toEqual({ error: "ask_unavailable" });
    expect(spendWrites()).toHaveLength(0);
  });

  it("a read that hasn't returned by 8,500 ms gives 503 ask_unavailable", async () => {
    w.stopped.add("model-calls");
    // The two counters take 8,490 ms of the budget, so the read has 10 ms.
    ddbMock.on(UpdateCommand).callsFake(() => {
      clock += 4245;
      return {};
    });
    w.nearbyPins.mockReturnValue(new Promise(() => {}));

    const res = await ask({ question: "May baha ba?", here: HERE });

    expect(res.statusCode).toBe(503);
    expect(parsed(res)).toEqual({ error: "ask_unavailable" });
  });

  it("a late read in the tool gives 503, and still records the paid turn", async () => {
    w.steps.splice(0, w.steps.length, step(callReply(), { takes: 8495 }));
    w.nearbyPins.mockReturnValue(new Promise(() => {}));

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(503);
    expect(spendWrites().map((input) => input.ExpressionAttributeValues?.[":n"])).toEqual([3498]);
  });
});

describe("the place lookup (spec §4.2, C736)", () => {
  it("a geocode that hasn't returned by the model mark gives lookup_unavailable, and still records the paid turn", async () => {
    // The geocoder's AWS calls have no request timeout of their own. This geocode never settles; it moves the
    // manual clock to 10 ms before the model mark, so the mark is a few real milliseconds away.
    w.geocode.mockImplementation(() => {
      clock = START + BUDGET.modelBy - 10;
      return new Promise(() => {});
    });
    w.steps.splice(0, w.steps.length, step(callReply({ place: UNLISTED })));
    const started = performance.now();

    const res = await ask({ question: `Baha ba sa ${UNLISTED}?` });

    expect(performance.now() - started).toBeLessThan(1000);
    expect(res.statusCode).toBe(200);
    expect(parsed(res).answer).toMatchObject({ source: "model", kind: "lookup_unavailable" });
    expect(w.nearbyPins).not.toHaveBeenCalled();
    expect(lastAskLine()).toMatchObject({ status: 200, nominatim: "failed", final: "skipped", tool_calls: 1, meta_calls: 1 });
    expect(linesWith("geocode_late")).toEqual([{ msg: "geocode_late", error: "MarkPassed" }]);
    // Turn 1 only, since the final turn had no time: 1,285 in and 445 out, 3,498 micro-dollars.
    expect(spendWrites().map((input) => input.ExpressionAttributeValues?.[":n"])).toEqual([3498]);
  });
});

describe("spend (spec C736)", () => {
  it("pauses at the spend threshold before any Meta call", async () => {
    spendMock.on(GetCommand).resolves({ Item: { pk: "spend#meta", micro_usd: 60_000_000, seeded: true } });

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(200);
    expect(parsed(res).answer).toMatchObject({ source: "plain_list", fallback: "model_calls_paused", kind: "reports" });
    expect(w.modelKey.get).not.toHaveBeenCalled();
    expect(w.createMeta).not.toHaveBeenCalled();
    expect(pauses()).toEqual([{ name: "/lusot/stop/model-calls", value: "on", overwrite: true }]);
    expect(linesWith("spend_stop")).toEqual([{ msg: "spend_stop", source: "ask", total_usd: "60", stop_usd: "60" }]);
    expect(spendWrites()).toHaveLength(0);
    expect(lastAskLine()).toMatchObject({ fallback: "model_calls_paused", meta_calls: 0 });
    // The counter is read strongly consistent, on the spend client.
    expect(spendMock.commandCalls(GetCommand)[0].args[0].input).toEqual({ TableName: "limits", Key: { pk: "spend#meta" }, ConsistentRead: true });
  });

  it.each([
    ["an unseeded counter", () => spendMock.on(GetCommand).resolves({ Item: { pk: "spend#meta", micro_usd: 5 } }), { unseeded: true }],
    ["no counter at all", () => spendMock.on(GetCommand).resolves({}), { unseeded: true }],
    [
      "an unreadable counter",
      () => spendMock.on(GetCommand).rejects(awsError("ProvisionedThroughputExceededException", 400)),
      { unreadable: { error: "ProvisionedThroughputExceededException", status: 400 } },
    ],
    [
      "an unreadable stop",
      () => ssmMock.on(GetParameterCommand, { Name: SPEND_STOP_PARAM }).rejects(awsError("AccessDeniedException", 400)),
      { unreadable: { error: "AccessDeniedException", status: 400 } },
    ],
    [
      "a stop that isn't a number",
      () => ssmMock.on(GetParameterCommand, { Name: SPEND_STOP_PARAM }).resolves({ Parameter: { Value: "sixty" } }),
      { unreadable: { error: "RangeError" } },
    ],
  ])("%s pauses too", async (_name, arrange, detail) => {
    arrange();

    const res = await ask({ question: QUESTION });

    expect(parsed(res).answer).toMatchObject({ source: "plain_list", fallback: "model_calls_paused" });
    expect(w.createMeta).not.toHaveBeenCalled();
    expect(pauses()).toHaveLength(1);
    expect(linesWith("spend_stop")).toEqual([{ msg: "spend_stop", source: "ask", ...detail }]);
  });

  it("a pause whose switch can't be set says so, and still answers", async () => {
    spendMock.on(GetCommand).resolves({});
    ssmMock.on(PutParameterCommand).rejects(awsError("AccessDeniedException", 400));

    const res = await ask({ question: QUESTION });

    expect(parsed(res).answer.fallback).toBe("model_calls_paused");
    expect(linesWith("spend_stop")).toEqual([
      { msg: "spend_stop", source: "ask", unseeded: true, switch: { error: "AccessDeniedException", status: 400 } },
    ]);
  });

  it("records a question's cost", async () => {
    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(200);
    // 3,182 in and 765 out: $0.00722875, rounded up to 7,229 micro-dollars, on the spend client only.
    expect(spendWrites()).toEqual([
      {
        TableName: "limits",
        Key: { pk: "spend#meta" },
        UpdateExpression: "ADD #micro :n",
        ExpressionAttributeNames: { "#micro": "micro_usd" },
        ExpressionAttributeValues: { ":n": 7229 },
        ReturnValues: "UPDATED_NEW",
      },
    ]);
    expect(counterKeys().every((key) => key.startsWith("question#"))).toBe(true);
    expect(w.lines.filter((line) => line.includes('"spend_source":"ask"'))).toHaveLength(1);
    expect(pauses()).toEqual([]);
  });

  it("charges every try with no answer at the unreported amount", async () => {
    w.steps.splice(0, w.steps.length, step(callReply(), { tries: [null] }), step(verdictReply()));

    await ask({ question: QUESTION });

    // 7,229 for the two answers, plus 20,000 in and 4,000 out for the lost try: 42,000.
    expect(spendWrites().map((input) => input.ExpressionAttributeValues?.[":n"])).toEqual([7229 + 42000]);
  });

  it("a total that reaches the stop after the write pauses at once", async () => {
    spendMock.on(UpdateCommand).resolves({ Attributes: { micro_usd: 60_000_500 } });

    const res = await ask({ question: QUESTION });

    expect(parsed(res).answer.source).toBe("model");
    expect(pauses()).toHaveLength(1);
    expect(linesWith("spend_stop")).toEqual([{ msg: "spend_stop", source: "ask", total_usd: "60.0005", stop_usd: "60" }]);
  });

  it("keeps the answer and sets the stop when the spend write still fails", async () => {
    spendMock.on(UpdateCommand).rejects(awsError("ProvisionedThroughputExceededException", 400));

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(200);
    expect(parsed(res).answer).toMatchObject({ source: "model", kind: "reports", cited: [w.pins[0].id, w.pins[1].id] });
    expect(pauses()).toEqual([{ name: "/lusot/stop/model-calls", value: "on", overwrite: true }]);
    expect(linesWith("spend_error")).toEqual([
      { msg: "spend_error", source: "ask", usd: "0.007229", error: "ProvisionedThroughputExceededException", status: 400 },
    ]);
    expect(lastAskLine()).toMatchObject({ status: 200, source: "model" });
  });

  // The settle is bounded (the review's Important 1): a late answer plus a write that keeps retrying, then a pause
  // that does too, must still end inside the API function's 15 s, with the failure on the log and the pause set.
  // The pins read moves the manual clock, so each mark is a few real milliseconds away.
  const pinsReadAt = (ms: number) =>
    w.nearbyPins.mockImplementation(async () => {
      clock = START + ms;
      return w.pins;
    });

  it("a spend write still out at the settle mark is a failed write: spend_error with the amount, then the pause", async () => {
    spendMock.on(UpdateCommand).callsFake(() => new Promise(() => {}));
    pinsReadAt(BUDGET.settleBy - 10);

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(200);
    expect(parsed(res).answer).toMatchObject({ source: "model", kind: "reports" });
    expect(spendWrites()).toHaveLength(1);
    // Turn 1 only, since the final turn had no time: 1,285 in and 445 out, 3,498 micro-dollars.
    expect(linesWith("spend_error")).toEqual([{ msg: "spend_error", source: "ask", usd: "0.003498", error: "MarkPassed" }]);
    expect(pauses()).toEqual([{ name: "/lusot/stop/model-calls", value: "on", overwrite: true }]);
    expect(lastAskLine()).toMatchObject({ status: 200, final: "skipped" });
  });

  it("a spend write that fails after the settle mark raises no unhandled rejection", async () => {
    spendMock.on(UpdateCommand).callsFake(
      () => new Promise((_, reject) => setTimeout(() => reject(awsError("ProvisionedThroughputExceededException", 400)), 30)),
    );
    pinsReadAt(BUDGET.settleBy - 10);

    await ask({ question: QUESTION });
    await new Promise((resolve) => setTimeout(resolve, 60)); // the write fails now, after the answer

    expect(linesWith("spend_error")).toEqual([{ msg: "spend_error", source: "ask", usd: "0.003498", error: "MarkPassed" }]);
  });

  it("a pause whose switch isn't set by the pause mark doesn't hold the answer", async () => {
    spendMock.on(UpdateCommand).rejects(awsError("ProvisionedThroughputExceededException", 400));
    ssmMock.on(PutParameterCommand).callsFake(() => new Promise(() => {}));
    pinsReadAt(BUDGET.pauseBy - 10);
    const started = performance.now();

    const res = await ask({ question: QUESTION });

    expect(performance.now() - started).toBeLessThan(1000);
    expect(res.statusCode).toBe(200);
    expect(parsed(res).answer).toMatchObject({ source: "model", kind: "reports" });
    expect(pauses()).toHaveLength(1);
    expect(linesWith("spend_error")).toEqual([
      {
        msg: "spend_error",
        source: "ask",
        usd: "0.003498",
        error: "ProvisionedThroughputExceededException",
        status: 400,
        switch: { error: "MarkPassed" },
      },
    ]);
  });

  it("gives the spend counter its own client: 5 attempts, each bounded at 1 s", () => {
    expect(SPEND_CLIENT_CONFIG).toEqual({
      maxAttempts: 5,
      requestHandler: { connectionTimeout: 1000, requestTimeout: 1000, throwOnRequestTimeout: true },
    });
  });

  it("retries a throttled spend write and counts it once", async () => {
    // A real client with the spend config, over a fake transport: the first ADD is throttled (DynamoDB applied
    // nothing), and the SDK's retry lands the second.
    let micro = 3_000_000;
    const targets: string[] = [];
    const reply = (statusCode: number, body: unknown) => ({
      response: { statusCode, headers: { "content-type": "application/x-amz-json-1.0" }, body: Buffer.from(JSON.stringify(body)) },
    });
    const transport = {
      async handle(req: { headers: Record<string, string>; body?: unknown }) {
        const target = req.headers["x-amz-target"];
        targets.push(target);
        if (target === "DynamoDB_20120810.GetItem") {
          return reply(200, { Item: { pk: { S: "spend#meta" }, micro_usd: { N: String(micro) }, seeded: { BOOL: true } } });
        }
        if (targets.filter((t) => t === "DynamoDB_20120810.UpdateItem").length === 1) {
          return reply(400, { __type: "com.amazonaws.dynamodb.v20120810#ProvisionedThroughputExceededException", message: "Rate exceeded" });
        }
        micro += Number(JSON.parse(String(req.body)).ExpressionAttributeValues[":n"].N);
        return reply(200, { Attributes: { micro_usd: { N: String(micro) } } });
      },
      updateHttpClientConfig() {},
      httpHandlerConfigs() {
        return {};
      },
    };
    const real = DynamoDBDocumentClient.from(
      new DynamoDBClient({
        ...SPEND_CLIENT_CONFIG,
        requestHandler: transport as unknown as DynamoDBClientConfig["requestHandler"],
        region: "ap-southeast-1",
        credentials: { accessKeyId: "test", secretAccessKey: "test" },
      }),
    );

    const res = await ask({ question: QUESTION }, { spendDdb: real });

    expect(res.statusCode).toBe(200);
    expect(targets).toEqual(["DynamoDB_20120810.GetItem", "DynamoDB_20120810.UpdateItem", "DynamoDB_20120810.UpdateItem"]);
    expect(micro).toBe(3_000_000 + 7229);
    expect(w.lines.filter((line) => line.includes('"spend_source":"ask"'))).toHaveLength(1);
    expect(linesWith("spend_error")).toEqual([]);
    expect(pauses()).toEqual([]);
  });

  it("anything else runAgent throws charges each try that may have been billed, then answers 500 internal", async () => {
    // A 200 the SDK couldn't read: a lost try (may be billed), a 503 (not billed), then the 200.
    w.steps.splice(0, w.steps.length, step(new TypeError("unreadable answer"), { tries: [null, 503] }));

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(500);
    expect(parsed(res)).toEqual({ error: "internal" });
    expect(spendWrites().map((input) => input.ExpressionAttributeValues?.[":n"])).toEqual([2 * 42000]);
    expect(lastAskLine()).toMatchObject({ status: 500, code: "internal", error: "TypeError", meta_calls: 3 });
    expect(w.lines.join("\n")).not.toContain("unreadable answer");
  });

  it("a tool that throws anything but the pins read after a paid turn records the turn, then answers 500 internal", async () => {
    // A bug in the place lookup, after turn 1 was paid.
    w.geocode.mockRejectedValue(new TypeError("x"));
    w.steps.splice(0, w.steps.length, step(callReply({ place: UNLISTED })));

    const res = await ask({ question: `Baha ba sa ${UNLISTED}?` });

    expect(res.statusCode).toBe(500);
    expect(parsed(res)).toEqual({ error: "internal" });
    // ask_call.json: 1,285 in and 445 out, 3,498 micro-dollars.
    expect(spendWrites().map((input) => input.ExpressionAttributeValues?.[":n"])).toEqual([3498]);
    expect(lastAskLine()).toMatchObject({ status: 500, code: "internal", error: "TypeError", tool_calls: 1, meta_calls: 1, input_tokens: 1285 });
  });

  it("a tool that throws on its second call records both paid turns", async () => {
    // Turn 2 calls get_reports again (Task 10's M5), and that call's pins read fails.
    w.steps.splice(0, w.steps.length, step(callReply()), step(callReply()));
    w.nearbyPins.mockResolvedValueOnce(w.pins).mockRejectedValueOnce(awsError("ProvisionedThroughputExceededException", 400));

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(503);
    expect(parsed(res)).toEqual({ error: "ask_unavailable" });
    // Two ask_call.json turns: 2,570 in and 890 out, $0.006995: 6,995 micro-dollars.
    expect(spendWrites().map((input) => input.ExpressionAttributeValues?.[":n"])).toEqual([6995]);
    expect(lastAskLine()).toMatchObject({ status: 503, tool_calls: 2, meta_calls: 2, input_tokens: 2 * 1285, output_tokens: 2 * 445 });
  });

  it("a counter that fails answers 500 internal, logged by the error's name", async () => {
    ddbMock.on(UpdateCommand).rejects(awsError("AccessDeniedException", 400));

    const res = await ask({ question: QUESTION });

    expect(res.statusCode).toBe(500);
    expect(parsed(res)).toEqual({ error: "internal" });
    expect(w.createMeta).not.toHaveBeenCalled();
    expect(lastAskLine()).toMatchObject({ status: 500, code: "internal", error: "AccessDeniedException" });
    expect(w.lines.join("\n")).not.toContain("arn:");
  });
});

describe("privacy (spec AK7)", () => {
  const SENTINEL_WORD = "Sentinelquestionword";
  const SENTINEL_DEVICE = "device-5e771ne1-0123456789";
  const SENTINEL_HERE = { lat: 14.6095123, lng: 120.9894123, accuracyM: 20 };
  const SECRETS = [SENTINEL_WORD, "14.6095123", "120.9894123", SENTINEL_DEVICE];

  it("no question, coordinate or device id reaches a log line or a DynamoDB call", async () => {
    const question = `${SENTINEL_WORD} baha ba dito sa España cor. Maceda?`;
    // The model's path, the plain list's, a failed pins read and a failed spend write.
    w.steps.splice(0, w.steps.length, step(callReply({ place: "", here: true })), step(verdictReply()));
    await ask({ question, here: SENTINEL_HERE }, {}, SENTINEL_DEVICE);
    w.stopped.add("model-calls");
    await ask({ question, here: SENTINEL_HERE }, {}, SENTINEL_DEVICE);
    w.nearbyPins.mockRejectedValue(awsError("AccessDeniedException", 400));
    await ask({ question, here: SENTINEL_HERE }, {}, SENTINEL_DEVICE);
    w.stopped.clear();
    w.nearbyPins.mockImplementation(async () => w.pins);
    w.steps.splice(0, w.steps.length, step(callReply()), step(verdictReply()));
    spendMock.on(UpdateCommand).rejects(awsError("AccessDeniedException", 400));
    await ask({ question, here: SENTINEL_HERE }, {}, SENTINEL_DEVICE);

    const hash = createHash("sha256").update(SENTINEL_DEVICE).digest("hex");
    expect(askLines()).toHaveLength(4);
    const logged = w.lines.join("\n");
    for (const secret of [...SECRETS, hash, ESPANA.name, ESPANA.id, "España", ...w.pins.map((p) => p.id), "r1"]) {
      expect(logged, secret).not.toContain(secret);
    }
    const stored = JSON.stringify([...ddbMock.calls(), ...spendMock.calls(), ...ssmMock.calls()].map((call) => call.args[0].input));
    for (const secret of SECRETS) expect(stored, secret).not.toContain(secret);
  });
});

describe("the log line (spec §4.9)", () => {
  it("one line per request, with only the spec's keys; only a question_cap refusal holds that term", async () => {
    const allowed = ["msg", ...ASK_LOG_FIELDS];
    await ask({ question: QUESTION });
    await ask("{not json");
    w.stopped.add("model-calls");
    await ask({ question: "May baha ba?" });
    w.stopped.clear();
    w.steps.splice(0, w.steps.length, step(new MetaError(503)));
    await ask({ question: QUESTION });
    ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
      if (!String(input.Key?.pk).includes("#ALL#")) throw conditionFailed();
      return {};
    });
    await ask({ question: QUESTION });
    const before = w.lines.length;

    expect(askLines()).toHaveLength(5);
    for (const line of askLines()) for (const key of Object.keys(line)) expect(allowed, key).toContain(key);
    expect(w.lines.filter((line) => line.includes("question_cap"))).toEqual([]);

    ddbMock.on(UpdateCommand).callsFake((input: UpdateCommandInput) => {
      if (String(input.Key?.pk).includes("#ALL#")) throw conditionFailed();
      return {};
    });
    await ask({ question: QUESTION });

    const capLines = w.lines.slice(before).filter((line) => line.includes("question_cap"));
    expect(capLines).toHaveLength(1);
    expect(JSON.parse(capLines[0])).toMatchObject({ msg: "ask", status: 429, code: "question_cap" });
  });
});

describe("the Nominatim viewbox", () => {
  it("NCR_BOUNDS are data/ncr.json's bounds", () => {
    const points = (ncr.coordinates as number[][][][]).flat(2);
    expect(NCR_BOUNDS).toEqual({
      west: Math.min(...points.map(([lng]) => lng)),
      south: Math.min(...points.map(([, lat]) => lat)),
      east: Math.max(...points.map(([lng]) => lng)),
      north: Math.max(...points.map(([, lat]) => lat)),
    });
  });
});
