import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { GetParameterCommand, PutParameterCommand, type SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient } from "@aws-sdk/lib-dynamodb";
import { json, type JsonResponse } from "../http";
import { giveBack, type LimitDeps, take } from "../limits";
import { logError } from "../log";
import type { ModelKey } from "../modelKey";
import type { PublicPin } from "../pins";
import { costOf, recordSpend, SpendUnseeded, spendTotal, toMicro, UNREPORTED_USAGE } from "../spend";
import type { StopSwitch } from "../stopSwitch";
import { type AgentResult, AgentToolError, type AgentUsage, runAgent } from "./agent";
import { type Answer, classify, type Fallback, noSpeech, plainList } from "./answer";
import { BUDGET, Deadline } from "./deadline";
import { type AskLogField, logAsk } from "./log";
import { type Meta, type MetaCall, type MetaDeps, MetaError, MODEL, TRANSCRIBE_MODEL } from "./meta";
import type { Geocoder, GeoTrace } from "./nominatim";
import { loadPrompts } from "./prompts";
import { parseQuestion, parseVoice } from "./request";
import { findSpotIn, type Spot, spotKeywords } from "./spots";
import { type Here, runGetReports, type ToolArgs, type ToolCtx, type ToolResult } from "./tool";
import { checkWav } from "./wav";
import { hasHereWords } from "./words";

// The Meta spend stop, in USD (MS4's template and spend.py's SPEND_STOP_PARAM).
export const SPEND_STOP_PARAM = "/lusot/spend/stop-usd";

// Meta's names for the two languages a spoken question is in (spec §4.7; its Speech to text page lists Tagalog, not
// Filipino).
export const LANGUAGE_BIAS = ["Tagalog", "English"];

// Metro Manila's bounds, from data/ncr.json (Task 0's notes): Nominatim's viewbox preference.
export const NCR_BOUNDS = { west: 120.906221, south: 14.347255, east: 121.135023, north: 14.785336 };

// spend.py's SPEND_CONFIG for the spend path's own clients (C736): 5 attempts in all, which ride out a throttle on
// the shared 2-unit limits table, each bounded at 1 s to connect and 1 s for the request. Without
// throwOnRequestTimeout the SDK would only warn when a request runs past its timeout.
export const SPEND_CLIENT_CONFIG = {
  maxAttempts: 5,
  requestHandler: { connectionTimeout: 1000, requestTimeout: 1000, throwOnRequestTimeout: true },
};

// The spend counter's own DynamoDB client, so a hung or throttled write stays bounded and other routes keep the
// SDK's default client (C736).
export function createSpendDdb(): DynamoDBDocumentClient {
  return DynamoDBDocumentClient.from(new DynamoDBClient(SPEND_CLIENT_CONFIG));
}

export type AskDeps = LimitDeps & {
  isStopped: StopSwitch;
  // MS4's nearbyPins over its PinDeps, the publish switch applied inside it.
  nearbyPins: (lat: number, lng: number, radiusM: number) => Promise<PublicPin[]>;
  inMetroManila: (lat: number, lng: number) => boolean;
  spots: Spot[];
  geocoder: Geocoder;
  modelKey: ModelKey;
  // createMeta, called once per question, so its `calls` hold only that question's tries.
  createMeta: (deps: MetaDeps) => Meta;
  // The spend counter's own client, and the SSM client that reads the stop and sets the model-calls switch.
  spendDdb: DynamoDBDocumentClient;
  ssm: SSMClient;
  stopParamPrefix: string;
  now: () => number;
  sleep: (ms: number) => Promise<void>;
  random: () => number;
};

// The decoded body and X-Lusot-Device, as index.ts reads them from the event.
export type AskRequest = { body: string | undefined; device: string | undefined };

type Line = Partial<Record<AskLogField, unknown>>;

// One question's state: what it asked, its budget, and its log line as it fills. A spoken question also holds its
// clip's length, which its transcription is billed by, and its transcript, which its answer carries.
type Question = {
  text: string;
  here?: Here;
  nowS: number;
  deadline: Deadline;
  deps: AskDeps;
  line: Line;
  clipMs?: number;
  transcript?: string;
};
type Route = (req: AskRequest, deps: AskDeps, deadline: Deadline, line: Line) => Promise<JsonResponse>;

const NO_USAGE: AgentUsage = { input: 0, output: 0, reasoning: 0 };
// The plain list's own lookup: the whole window (C732 needs the model's reading to shorten it), and no model parts.
const PLAIN_ARGS: ToolArgs = { place: "", here: false, sinceMin: 180, kind: "depth", vehicle: "none" };

// POST /ask, typed (spec §4.1): check the body, count the question, then the model's answer or the plain list.
// Every path writes one log line (§4.9). Anything that throws is MS1's 500 internal, logged by its name only.
export async function askTyped(req: AskRequest, deps: AskDeps): Promise<JsonResponse> {
  return handle("ask", typed, req, deps);
}

// POST /ask/voice (spec §4.1, §4.7): check the clip, then the pauses, before anything is counted, since transcription
// is a Meta call; count it, transcribe it by 7 s, and answer the transcript as a typed question, with the transcript,
// by marks voiceExtra later (deadline.ts).
export async function askVoice(req: AskRequest, deps: AskDeps): Promise<JsonResponse> {
  return handle("ask_voice", spoken, req, deps);
}

async function handle(route: "ask" | "ask_voice", run: Route, req: AskRequest, deps: AskDeps): Promise<JsonResponse> {
  const startMs = deps.now();
  const line: Line = { route, meta_calls: 0 };
  let res: JsonResponse;
  try {
    res = await run(req, deps, new Deadline(startMs, deps.now), line);
  } catch (err) {
    line.error = err instanceof Error ? err.name : "unknown";
    res = json(500, { error: "internal" });
  }
  logAsk({ ...line, status: res.statusCode, code: errorCode(res), ms: deps.now() - startMs });
  return res;
}

async function typed(req: AskRequest, deps: AskDeps, deadline: Deadline, line: Line): Promise<JsonResponse> {
  const parsed = parseQuestion(req.body);
  if ("detail" in parsed) return json(400, { error: "bad_request", detail: parsed.detail });

  // The device first, then the hour; a refusal costs nothing (C716).
  const nowS = Math.floor(deps.now() / 1000);
  const refused = await take("question", req.device, nowS, deps);
  if (refused !== null) return refused;

  const q: Question = { text: parsed.question, here: parsed.here, nowS, deadline, deps, line };
  if (await deps.isStopped("model-calls", deps.now())) return plainAnswer(q, "model_calls_paused");
  const stopUsd = await spendCheck(deps, deadline);
  if (stopUsd === null) return plainAnswer(q, "model_calls_paused");

  let key: string;
  try {
    key = await deps.modelKey.get(deadline.signal(BUDGET.modelBy));
  } catch (err) {
    logError("model_key_unreadable", err);
    return plainAnswer(q, "model_error");
  }
  return modelPath(q, deps.createMeta({ key, sleep: deps.sleep, random: deps.random, now: deps.now }), stopUsd);
}

async function spoken(req: AskRequest, deps: AskDeps, deadline: Deadline, line: Line): Promise<JsonResponse> {
  const parsed = parseVoice(req.body);
  if ("error" in parsed) return json(400, parsed.detail === undefined ? { error: parsed.error } : { error: parsed.error, detail: parsed.detail });
  const clip = checkWav(parsed.audio);
  if (!clip.ok) return json(clip.code === "bad_audio" ? 400 : 422, { error: clip.code });
  line.audio_ms = clip.durationMs;

  // Neither pause counts the question (spec §5.4): a spoken one can't be answered without Meta. The switch is read
  // first, from its 30 s cache. The spend counter is read only once the question is counted, so refused questions
  // can't drain the limits table's 2 read units and trip the fail-closed pause; a stop found then gives the count back.
  if (await deps.isStopped("model-calls", deps.now())) return json(503, { error: "voice_paused" });
  const nowS = Math.floor(deps.now() / 1000);
  const refused = await take("question", req.device, nowS, deps);
  if (refused !== null) return refused;
  const stopUsd = await spendCheck(deps, deadline);
  if (stopUsd === null) {
    try {
      await giveBack("question", req.device, nowS, deps);
    } catch (err) {
      logError("question_give_back_failed", err); // one question too many on the counters, never too few
    }
    return json(503, { error: "voice_paused" });
  }

  let key: string;
  try {
    key = await deps.modelKey.get(deadline.signal(BUDGET.transcribeBy));
  } catch (err) {
    logError("model_key_unreadable", err);
    return json(503, { error: "voice_failed" });
  }
  const meta = deps.createMeta({ key, sleep: deps.sleep, random: deps.random, now: deps.now });
  const q: Question = { text: "", here: parsed.here, nowS, deadline, deps, line, clipMs: clip.durationMs };

  const started = deps.now();
  let transcript: string;
  try {
    const opts = { keywords: spotKeywords(deps.spots), languageBias: LANGUAGE_BIAS };
    transcript = (await meta.transcribe(parsed.audio, opts, deadline, BUDGET.transcribeBy)).transcript.trim();
  } catch (err) {
    // A failed or late transcription is a 503 voice_failed (spec §5.4), after its billed tries are recorded. A
    // rejected key is dropped, as the model path drops it (C710). Anything else is a bug: MS1's 500.
    if (err instanceof MetaError && (err.status === 401 || err.status === 402 || err.status === 403)) deps.modelKey.drop();
    await settleTranscription(q, meta, stopUsd, started);
    if (!(err instanceof MetaError)) throw err;
    return json(503, { error: "voice_failed" });
  }

  if (transcript === "") {
    await settleTranscription(q, meta, stopUsd, started);
    Object.assign(line, { tool_calls: 0, final: null, crossing: null });
    return answered({ ...q, transcript }, noSpeech(), null);
  }
  line.transcribe_ms = deps.now() - started;
  // The model and answer marks come voiceExtra later for a spoken question (deadline.ts).
  return modelPath({ ...q, text: transcript, transcript, deadline: deadline.spoken() }, meta, stopUsd);
}

// A spoken question that ends at its transcription: its log fields, and its billed audio on the spend counter.
async function settleTranscription(q: Question, meta: Meta, stopUsd: number, started: number): Promise<void> {
  q.line.transcribe_ms = q.deps.now() - started;
  metaFields(meta, q.line);
  await settleSpend(NO_USAGE, billedAudioSeconds(meta, q.clipMs), stopUsd, q.deps, q.deadline);
}

// Transcription is billed by the clip's whole seconds (F5), for each try that may have been billed. A typed question
// has no clip. checkWav rounds the clip's length up to a whole ms, so its seconds round up here too, never under.
function billedAudioSeconds(meta: Meta, clipMs: number | undefined): number {
  if (clipMs === undefined) return 0;
  const tries = meta.calls.filter((call) => call.model === TRANSCRIBE_MODEL && mayBeBilled(call));
  return tries.length * Math.ceil(clipMs / 1000);
}

// A try Meta may have billed: any but its own HTTP error answer (backend/analysis's _maybe_billed), so a try with no
// answer counts.
function mayBeBilled(call: MetaCall): boolean {
  return call.status === null || call.status < 400;
}

// The tool loop, then the answer it gives. Whatever ends it, the question's cost goes to the spend counter.
async function modelPath(q: Question, meta: Meta, stopUsd: number): Promise<JsonResponse> {
  const { deps, line } = q;
  let usage = NO_USAGE;
  let trace: GeoTrace | null = null;
  const ctx = toolCtx(q);
  const tool = async (args: ToolArgs): Promise<ToolResult> => {
    const result = await runGetReports(args, ctx);
    trace = result.geo ?? trace; // a later call that didn't geocode keeps the earlier one's trace
    return result;
  };

  const modelStart = deps.now();
  try {
    let result: AgentResult;
    try {
      const dropKey = () => deps.modelKey.drop();
      result = await runAgent({ text: q.text, here: q.here }, { meta, prompts: loadPrompts(), tool, deadline: q.deadline, dropKey });
    } catch (err) {
      if (!(err instanceof AgentToolError)) {
        // A bug, or a 200 the SDK couldn't read: charge each try that may have been billed (C736: never under).
        const billed = meta.calls.filter((call) => call.model === MODEL && mayBeBilled(call)).length;
        const { spark_input_tokens: input, spark_output_tokens: output } = UNREPORTED_USAGE;
        usage = { input: billed * input, output: billed * output, reasoning: 0 };
        throw err;
      }
      usage = err.usage;
      line.tool_calls = err.toolCalls;
      if (!(err.cause instanceof PinsUnavailable)) throw err.cause;
      return unavailable(err.cause);
    } finally {
      line.model_ms = deps.now() - modelStart;
      metaFields(meta, line);
    }
    usage = result.usage;
    line.tool_calls = result.toolCalls;

    const { outcome } = result;
    if (outcome.type === "answer") {
      line.final = outcome.final;
      line.crossing = outcome.crossingFrom;
      return answered(q, outcome.answer, trace);
    }
    // Only turn 1 falls back, before any tool ran, so today a fallback carries no tool result. One that did would
    // keep the place the model's call found (spec §4.5).
    const { tool: found, fallback } = outcome;
    if (found !== undefined) {
      plainLine(q);
      return answered(q, plainList(found, q.text, fallback), trace);
    }
    return await plainAnswer(q, fallback);
  } finally {
    line.input_tokens = usage.input;
    line.output_tokens = usage.output;
    line.reasoning_tokens = usage.reasoning;
    await settleSpend(usage, billedAudioSeconds(meta, q.clipMs), stopUsd, deps, q.deadline);
  }
}

// The plain list with its own place (spec §4.5): the longest spot name in the question. A "here" word, or no spot
// found while a location was sent, means the phone's location; a "here" word without one gives no_location, as the
// model's `here: true` call does. Never Nominatim: without the model, code can't tell which words are a place.
async function plainAnswer(q: Question, fallback: Fallback): Promise<JsonResponse> {
  const spot = findSpotIn(q.text, q.deps.spots);
  let args: ToolArgs | undefined;
  if (hasHereWords(q.text) || (spot === undefined && q.here !== undefined)) args = { ...PLAIN_ARGS, here: true };
  else if (spot !== undefined) args = { ...PLAIN_ARGS, place: spot.name };

  let tool: ToolResult | undefined;
  if (args !== undefined) {
    try {
      tool = await runGetReports(args, { ...toolCtx(q), geocoder: undefined });
    } catch (err) {
      if (!(err instanceof PinsUnavailable)) throw err;
      return unavailable(err);
    }
  }
  plainLine(q);
  return answered(q, plainList(tool, q.text, fallback), null);
}

// The plain list's log fields: no final turn, and the crossing line from the words only. tool_calls keeps the
// model's count when it ran, else 0.
function plainLine(q: Question): void {
  const crossing = classify({ calls: [], question: q.text }).crossingFrom;
  Object.assign(q.line, { tool_calls: q.line.tool_calls ?? 0, final: null, crossing });
}

// The 200 and its log fields. A spoken question's answer carries its transcript (spec §5.2).
function answered(q: Question, a: Answer, trace: GeoTrace | null): JsonResponse {
  Object.assign(q.line, {
    source: a.source,
    fallback: a.fallback,
    kind: a.kind,
    vehicle: a.vehicle,
    place_source: a.place?.source ?? null,
    nominatim: trace,
    reports: a.reports.length,
    demo: a.demo.length,
    cited: a.cited.length,
  });
  return json(200, q.transcript === undefined ? { answer: a } : { answer: a, transcript: q.transcript });
}

function toolCtx(q: Question): ToolCtx {
  const { deps, deadline } = q;
  return {
    here: q.here,
    geocoder: byModelMark(deps.geocoder),
    nearbyPins: (lat, lng, radiusM) => byAnswerMark(deps.nearbyPins(lat, lng, radiusM), deadline),
    inMetroManila: deps.inMetroManila,
    spots: deps.spots,
    nowS: q.nowS,
    deadline,
  };
}

// --- the marks: the geocode by 7.5 s and the pins read by 8.5 s (spec §4.1; 11 s and 12 s for a spoken question,
// §4.7), the spend write by 12.5 s and the pause
// by 14 s (C736) ---------------------------------------------------------------------------------------------------

// A call that hadn't returned by its mark. Its name is what the log lines show.
class MarkPassed extends Error {
  constructor() {
    super("the call hadn't returned by its mark");
    this.name = "MarkPassed";
  }
}

// `work`'s result, or MarkPassed once the mark passes. The timer is cleared either way. Promise.race subscribes to
// `work`, so a work that fails after the mark raises no unhandled rejection; it may still land later, which for a
// spend write can only over-count.
async function byMark<T>(work: Promise<T>, deadline: Deadline, byMs: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const late = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new MarkPassed()), deadline.remainingMs(byMs));
  });
  try {
    return await Promise.race([work, late]);
  } finally {
    clearTimeout(timer);
  }
}

// The geocoder, bounded by the model mark. It runs after turn 1 is paid, and its cache, slot and switch reads have no
// request timeout of their own, so a stalled one would hold the question until Lambda's timeout, where the paid turn
// is never recorded (C736). A geocode still out at the mark is a failed one, so the tool answers lookup_unavailable
// (spec §4.2). Any other throw is a bug, and goes on to the handler with the usage.
function byModelMark(geocoder: Geocoder): Geocoder {
  return {
    async geocode(place, deadline) {
      try {
        return await byMark(geocoder.geocode(place, deadline), deadline, BUDGET.modelBy);
      } catch (err) {
        if (!(err instanceof MarkPassed)) throw err;
        logError("geocode_late", err);
        return { trace: "failed" };
      }
    },
  };
}

// The pins read failed, or hadn't returned by the answer mark: a 503 ask_unavailable (spec §5.4).
class PinsUnavailable extends Error {
  constructor(cause: unknown) {
    super("the pins couldn't be read in time", { cause });
    this.name = "PinsUnavailable";
  }
}

// The read, or PinsUnavailable once it fails or the answer mark passes. Only the read is bounded, never the tool
// loop, so the usage of the turns already paid always comes back (inside AgentToolError).
async function byAnswerMark(read: Promise<PublicPin[]>, deadline: Deadline): Promise<PublicPin[]> {
  try {
    return await byMark(read, deadline, BUDGET.answerBy);
  } catch (err) {
    throw new PinsUnavailable(err);
  }
}

function unavailable(err: PinsUnavailable): JsonResponse {
  logError("ask_pins_unavailable", err.cause);
  return json(503, { error: "ask_unavailable" });
}

// --- the log line's Meta fields (spec §4.9) ----------------------------------------------------------------------

// meta_calls counts every try. meta_status is the last try's status when that try failed (null for a timeout or a
// lost connection), so it is the error that ended the model path; it is left out when the last try answered.
function metaFields(meta: Meta, line: Line): void {
  line.meta_calls = meta.calls.length;
  const last = meta.calls.at(-1);
  if (last !== undefined && (last.status === null || last.status >= 400)) line.meta_status = last.status;
}

function errorCode(res: JsonResponse): string | undefined {
  const body = JSON.parse(res.body) as { error?: unknown };
  return typeof body.error === "string" ? body.error : undefined;
}

// --- spend (C736, MS4's C527) -----------------------------------------------------------------------------------

// Before the first Meta call: the stop in USD while the counter is under it, else null once model calls are paused.
// A total at or over the stop, or either one unreadable (an unseeded counter included), pauses: fail closed.
async function spendCheck(deps: AskDeps, deadline: Deadline): Promise<number | null> {
  let stop: number;
  let total: number;
  try {
    stop = await readStop(deps.ssm);
    total = await spendTotal({ ddb: deps.spendDdb, limitsTableName: deps.limitsTableName });
  } catch (err) {
    const fields = err instanceof SpendUnseeded ? { unseeded: true } : { unreadable: errorFields(err) };
    await pause(deps, deadline, "spend_stop", fields);
    return null;
  }
  if (total >= stop) {
    await pause(deps, deadline, "spend_stop", { total_usd: String(total), stop_usd: String(stop) });
    return null;
  }
  return stop;
}

async function readStop(ssm: SSMClient): Promise<number> {
  const { Parameter } = await ssm.send(new GetParameterCommand({ Name: SPEND_STOP_PARAM }));
  const text = Parameter?.Value?.trim() ?? "";
  const stop = text === "" ? Number.NaN : Number(text);
  if (!Number.isFinite(stop)) throw new RangeError("the spend stop isn't a number");
  return stop;
}

// After the question: its cost on the counter, under the source "ask": Muse Spark's tokens and the transcription's
// billed seconds, at MS4's PRICES (C736). Nothing billed records nothing. A total that
// reaches the stop pauses at once. A write that still fails after the client's retries, or is still out at the
// settle mark, logs spend_error with the amount and pauses (fail closed). The client's retries alone could run
// about 7.5 s, so the mark keeps a late answer's settle and pause inside the 15 s timeout, where a killed Lambda
// would record nothing and log nothing. The answer stands either way, so nothing here throws.
async function settleSpend(
  usage: AgentUsage,
  audioSeconds: number,
  stopUsd: number,
  deps: AskDeps,
  deadline: Deadline,
): Promise<void> {
  let cost: string | undefined;
  try {
    cost = costOf({ spark_input_tokens: usage.input, spark_output_tokens: usage.output, audio_seconds: audioSeconds });
    if (cost === "0") return;
    const write = recordSpend(cost, "ask", { ddb: deps.spendDdb, limitsTableName: deps.limitsTableName });
    const total = await byMark(write, deadline, BUDGET.settleBy);
    if (total >= stopUsd) await pause(deps, deadline, "spend_stop", { total_usd: String(total), stop_usd: String(stopUsd) });
  } catch (err) {
    const usd = cost === undefined ? null : String(toMicro(cost) / 1_000_000);
    await pause(deps, deadline, "spend_error", { usd, ...errorFields(err) });
  }
}

// Sets /lusot/stop/model-calls "on" and logs the reason as its own line, which MS4's SpendPauseAlarm counts by its
// msg. A put that fails, or is still out at the pause mark, is named on the line as `switch`; the line still
// reaches the alarm.
async function pause(
  deps: AskDeps,
  deadline: Deadline,
  msg: "spend_stop" | "spend_error",
  fields: Record<string, unknown>,
): Promise<void> {
  const out: Record<string, unknown> = { msg, source: "ask", ...fields };
  try {
    const put = new PutParameterCommand({ Name: `${deps.stopParamPrefix}model-calls`, Value: "on", Type: "String", Overwrite: true });
    await byMark(deps.ssm.send(put), deadline, BUDGET.pauseBy);
  } catch (err) {
    out.switch = errorFields(err);
  }
  console.error(JSON.stringify(out));
}

// An error by its name and HTTP status only: an AWS message can hold an ARN.
function errorFields(err: unknown): { error: string; status?: number } {
  return {
    error: err instanceof Error ? err.name : "unknown",
    status: (err as { $metadata?: { httpStatusCode?: number } } | undefined)?.$metadata?.httpStatusCode,
  };
}
