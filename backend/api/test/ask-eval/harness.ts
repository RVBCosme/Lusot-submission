// Ask Lusot's typed harness (Task 18; spec AK1, C728): the 10 typed questions in questions.json through the real
// handler, with the fixture pins (pins.json), the fixture geocoder (geocodes.json, so no Nominatim request) and the
// question limits in memory. Meta, the spend counter and SSM are the caller's: ask-eval.test.ts passes the real Meta
// client and the deployed stack's counter and switches (C527, C736); fixtures.test.ts's dry run passes a fake Meta and
// mocked AWS clients. Each answer goes to <data>\ask\<date>\answers.jsonl, outside the repo. Stdout gets counts and
// timings only: never a question, an answer, a place or a handler log line.
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { format } from "node:util";
import { GetParameterCommand, type SSMClient } from "@aws-sdk/client-ssm";
import { type DynamoDBDocumentClient, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import type { Answer } from "../../src/ask/answer";
import { type AskDeps, askTyped, SPEND_STOP_PARAM } from "../../src/ask/handler";
import { createMeta } from "../../src/ask/meta";
import type { Box, Geocoder } from "../../src/ask/nominatim";
import { SPOTS } from "../../src/ask/spots";
import { normalize } from "../../src/ask/text";
import { inMetroManila } from "../../src/metroManila";
import { distanceM, type Point, type PublicPin } from "../../src/pins";
import { costOf, spendTotal, toMicro, UNREPORTED_USAGE } from "../../src/spend";
import { createStopSwitch } from "../../src/stopSwitch";

export const STOP_PREFIX = "/lusot/stop/"; // the template's STOP_PARAM_PREFIX
const DEVICE = "ask-eval-harness"; // one device for the run, counted in memory only
const TIME_LIMIT_MS = 10_000; // plan §12's 10 s, around the handler call (AK1)
const TURNS_AT_MOST = 3; // C703: at most three Meta turns a question
const MAX_PINS = 200; // MS4's nearby read
const M_PER_DEGREE = (6_371_008.8 * Math.PI) / 180; // MS4's mean radius, so the offsets match distanceM
const REPO = fileURLToPath(new URL("../../../../", import.meta.url));

// --- the fixtures ----------------------------------------------------------------------------------------------

type PlaceSource = "spots" | "nominatim" | "here";

export type Expect = {
  kind: Answer["kind"];
  // The place: a spots.json id with "spots", a geocodes.json id with "nominatim", no id with "here", and null for an
  // answer without a place. Left out, the place isn't checked.
  placeSource?: PlaceSource | null;
  placeId?: string;
  crossing: boolean;
  vehicle: Answer["vehicle"];
  // For an answer from a lookup: the live reports counted, the summary's pin and the demo pins shown.
  count?: number;
  deepest?: string;
  demo?: number;
  // For place_too_broad: the listed spots offered, by id, in any order.
  suggestions?: string[];
};

export type TypedQuestion = { id: string; route: "ask"; text: string; here: "fixture" | null; expect: Expect };

type FixturePin = {
  id: string;
  at: string; // "spot:<id>", "here" or "geocode:<id>"
  northM: number;
  eastM: number;
  mode: "live" | "demo";
  minutesAgo?: number; // a live pin's
  capturedAt?: string; // a demo pin's own date
  level: string;
  levelIsFloor: boolean;
  landmark: string;
  credit?: string;
  place?: string;
  event?: string;
};

export type PinsFixture = { here: { lat: number; lng: number; accuracyM: number }; pins: FixturePin[] };

// What Nominatim would answer for a place holding every one of `words`.
export type GeocodeFixture = { id: string; words: string[]; name: string; lat: number; lng: number; box: Box };

const readJson = <T>(name: string): T => JSON.parse(readFileSync(new URL(name, import.meta.url), "utf8")) as T;
export const loadQuestions = (): TypedQuestion[] => readJson("questions.json");
export const loadPins = (): PinsFixture => readJson("pins.json");
export const loadGeocodes = (): GeocodeFixture[] => readJson("geocodes.json");

// A box's diagonal in metres, as nominatim.ts measures a result's span.
export const spanOf = (box: Box): number => distanceM({ lat: box.south, lng: box.west }, { lat: box.north, lng: box.east });

// eval/rules.md §1's class for each level (MS3a's rules.PASSABILITY).
const CLASS_OF: Record<string, string> = {
  below_gutter: "PATV",
  gutter: "PATV",
  half_knee: "PATV",
  half_tire: "NPLV",
  knee: "NPLV",
  tire: "NPATV",
  waist: "NPATV",
  chest: "NPATV",
  above_chest: "NPATV",
};
// Table 8's people rows; any other landmark is a wheel's or a vehicle body's.
const PERSON_LANDMARKS = new Set(["ankle", "mid_shin", "knee", "mid_thigh", "waist", "chest", "above_chest"]);

function anchorOf(at: string, fixture: PinsFixture, geocodes: GeocodeFixture[]): Point {
  if (at === "here") return fixture.here;
  const [kind, id] = at.split(":");
  const found = kind === "spot" ? SPOTS.find((s) => s.id === id) : kind === "geocode" ? geocodes.find((g) => g.id === id) : undefined;
  if (found === undefined) throw new Error(`pins.json: no anchor ${at}`);
  return found;
}

const round4 = (value: number): number => Math.round(value * 10_000) / 10_000;

// The fixture pins as MS4's public pins at `nowMs`: placed by their offsets, rounded to 4 decimals as publicPin rounds.
export function fixturePins(nowMs: number, fixture = loadPins(), geocodes = loadGeocodes()): PublicPin[] {
  return fixture.pins.map((p) => {
    const anchor = anchorOf(p.at, fixture, geocodes);
    const capturedAt = p.mode === "demo" ? p.capturedAt : p.minutesAgo === undefined ? undefined : new Date(nowMs - p.minutesAgo * 60_000).toISOString();
    if (capturedAt === undefined || !(p.level in CLASS_OF)) throw new Error(`pins.json: ${p.id} needs its time and one of the nine levels`);
    const pin: PublicPin = {
      id: p.id,
      lat: round4(anchor.lat + p.northM / M_PER_DEGREE),
      lng: round4(anchor.lng + p.eastM / (M_PER_DEGREE * Math.cos((anchor.lat * Math.PI) / 180))),
      gpsAccuracyM: 10,
      capturedAt,
      mode: p.mode,
      level: p.level,
      landmark: p.landmark,
      passability: CLASS_OF[p.level],
      levelIsFloor: p.levelIsFloor,
      basis: PERSON_LANDMARKS.has(p.landmark) ? { vehicles: 0, people: 1 } : { vehicles: 1, people: 0 },
      flags: 0,
    };
    if (p.mode === "demo") Object.assign(pin, { credit: p.credit, place: p.place, event: p.event });
    return pin;
  });
}

// MS4's nearbyPins over the fixture pins: within radiusM of the point, newest first, at most 200. The fixture pins
// are never on the public map, so the publish switch has nothing to hide here.
function fixtureNearby(now: () => number, fixture: PinsFixture, geocodes: GeocodeFixture[]): AskDeps["nearbyPins"] {
  return async (lat, lng, radiusM) =>
    fixturePins(now(), fixture, geocodes)
      .filter((pin) => distanceM({ lat, lng }, pin) <= radiusM)
      .sort((a, b) => Date.parse(b.capturedAt) - Date.parse(a.capturedAt))
      .slice(0, MAX_PINS);
}

// Nominatim's answer from geocodes.json: the first entry whose every phrase is in the place as whole words of the
// normalised text, else not found. No request leaves the laptop, and no slot or cache item is touched.
function fixtureGeocoder(geocodes: GeocodeFixture[]): Geocoder {
  return {
    async geocode(place) {
      const text = ` ${normalize(place)} `;
      const hit = geocodes.find((g) => g.words.every((word) => text.includes(` ${normalize(word)} `)));
      if (hit === undefined) return { result: { status: "not_found" }, trace: "not_found" };
      const { name, lat, lng, box } = hit;
      return { result: { status: "found", name, lat, lng, box, spanM: spanOf(box) }, trace: "called" };
    },
  };
}

// MS4's question counters (take's UpdateCommands) held in memory, so the harness never writes to the limits table.
function memoryLimits(): DynamoDBDocumentClient {
  const counts = new Map<string, number>();
  const send = async (command: unknown) => {
    if (!(command instanceof UpdateCommand)) throw new Error("the in-memory limits take only UpdateCommand");
    const { Key, ConditionExpression, ExpressionAttributeValues: values = {} } = command.input;
    const pk = String(Key?.pk);
    const n = counts.get(pk) ?? 0;
    if (ConditionExpression !== undefined && n >= Number(values[":limit"])) {
      throw Object.assign(new Error("The conditional request failed"), { name: "ConditionalCheckFailedException" });
    }
    counts.set(pk, n + Number(values[":one"] ?? values[":minusOne"]));
    return {};
  };
  return { send } as unknown as DynamoDBDocumentClient;
}

// --- the guards ------------------------------------------------------------------------------------------------

// A refusal before anything is paid for. Its message is fixed, or names an AWS error by its name only.
export class HarnessRefused extends Error {
  constructor(message: string) {
    super(message);
    this.name = "HarnessRefused";
  }
}

// One path part names sealed as Windows reads it: in any case, by its name before any ":" (the NTFS stream
// sealed::$INDEX_ALLOCATION), without trailing dots and spaces (eval/data/guards.py's is_sealed_name).
const isSealedName = (part: string): boolean => part.split(":", 1)[0].replace(/[. ]+$/, "").toLowerCase() === "sealed";

// The answers file, <dataDir>\ask\<date>\answers.jsonl. Refused when a part of it, as given or made absolute, names
// sealed, or when the data folder lies inside the repo. It reads the strings only, never the disk.
export function answersPath(dataDir: string, date: string): string {
  const out = join(dataDir, "ask", date, "answers.jsonl");
  for (const form of [dataDir, out, resolve(out)]) {
    if (form.split(/[\\/]+/).some(isSealedName)) throw new HarnessRefused("refused: the output path is inside a folder named sealed");
  }
  const rel = relative(REPO.toLowerCase(), resolve(dataDir).toLowerCase());
  if (rel === "" || (rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel))) {
    throw new HarnessRefused("refused: the data folder is inside the repo");
  }
  return out;
}

const errorName = (err: unknown): string => (err instanceof Error ? err.name : "unknown");

// Before the first question (C527, C736), the stop and the total, read as the handler reads them. Refused, before
// any Meta call, when either can't be read, the total is at or over the stop, or `questions` worst cases would reach
// it: each question at most three turns, each charged as a reply whose usage Meta didn't report.
async function checkSpend(o: HarnessOptions, questions: number): Promise<void> {
  let stop: number;
  let total: number;
  try {
    const { Parameter } = await o.ssm.send(new GetParameterCommand({ Name: SPEND_STOP_PARAM }));
    const text = Parameter?.Value?.trim() ?? "";
    stop = text === "" ? Number.NaN : Number(text);
    total = await spendTotal({ ddb: o.spendDdb, limitsTableName: o.limitsTableName });
  } catch (err) {
    throw new HarnessRefused(`refused: the spend counter or its stop can't be read (${errorName(err)})`);
  }
  if (!Number.isFinite(stop)) throw new HarnessRefused("refused: the spend stop isn't a number");
  if (total >= stop) throw new HarnessRefused(`refused: the spend counter ($${total}) is at or over its stop ($${stop})`);
  const worstMicro = questions * TURNS_AT_MOST * toMicro(costOf(UNREPORTED_USAGE));
  if (Math.round(total * 1_000_000) + worstMicro >= Math.round(stop * 1_000_000)) {
    throw new HarnessRefused(`refused: ${questions} questions at worst ($${worstMicro / 1_000_000}) would reach the spend stop ($${stop}) from $${total}`);
  }
}

// --- the checks (AK1) ------------------------------------------------------------------------------------------

type CheckName = "status" | "time" | "notPaused" | "kind" | "place" | "crossing" | "vehicle" | "cited" | "count" | "deepest" | "demo" | "suggestions";
// Each check passed (true) or failed (false); null when it doesn't apply to this question or this answer.
type Checks = Record<CheckName, boolean | null>;

const spotName = (id: string): string | undefined => SPOTS.find((s) => s.id === id)?.name;

function placeMatches(e: Expect, place: Answer["place"], geocodes: GeocodeFixture[]): boolean {
  if (e.placeSource === null) return place === null;
  if (place === null || place.source !== e.placeSource) return false;
  if (e.placeSource === "spots") return e.placeId !== undefined && place.name === spotName(e.placeId);
  if (e.placeSource === "nominatim") return place.name === geocodes.find((g) => g.id === e.placeId)?.name;
  return true; // here
}

// Spec AK1: where a model answer has citations, they are among the reports it returned, the deepest among them. The
// plain list cites nothing.
function citedOk(a: Answer): boolean {
  if (a.source !== "model") return a.cited.length === 0;
  if (a.cited.length === 0) return true;
  const returned = new Set([...a.reports, ...a.demo].map((pin) => pin.id));
  return a.cited.every((id) => returned.has(id)) && (a.deepestId === null || a.cited.includes(a.deepestId));
}

const sameSet = (a: string[], b: string[]): boolean => a.length === b.length && [...a].sort().join("\n") === [...b].sort().join("\n");

// A model answer is held to every expectation. A plain list (spec §4.5) can't call Nominatim or say off_topic, so
// it passes on its status, time, place (the expected one, or none) and rules (the crossing line from the words, no
// vehicle, no citations), and counts as a model miss. A paused stack's plain list fails.
function check(q: TypedQuestion, status: number, ms: number, a: Answer | null, geocodes: GeocodeFixture[]): Checks {
  const e = q.expect;
  const checks: Checks = {
    status: status === 200,
    time: ms <= TIME_LIMIT_MS,
    notPaused: a?.fallback !== "model_calls_paused",
    kind: null,
    place: null,
    crossing: null,
    vehicle: null,
    cited: null,
    count: null,
    deepest: null,
    demo: null,
    suggestions: null,
  };
  if (a === null) return { ...checks, kind: false };
  const model = a.source === "model";
  if (e.placeSource !== undefined) checks.place = model || a.place !== null ? placeMatches(e, a.place, geocodes) : true;
  checks.crossing = a.crossing === e.crossing;
  checks.vehicle = a.vehicle === (model ? e.vehicle : null);
  checks.cited = citedOk(a);
  if (!model) return checks;
  checks.kind = a.kind === e.kind;
  if (e.count !== undefined) checks.count = a.count === e.count;
  if (e.deepest !== undefined) checks.deepest = a.deepestId === e.deepest;
  if (e.demo !== undefined) checks.demo = a.demo.length === e.demo;
  if (e.suggestions !== undefined) checks.suggestions = sameSet(a.suggestions, e.suggestions.map((id) => spotName(id) ?? id));
  return checks;
}

// --- the run ---------------------------------------------------------------------------------------------------

export type HarnessOptions = {
  dataDir: string;
  date: string; // YYYY-MM-DD, the answers' folder
  limitsTableName: string; // the spend counter's table
  spendDdb: DynamoDBDocumentClient; // the spend counter's own client (C736)
  ssm: SSMClient; // the spend stop, the pause and the stop switches
  key: string; // the Meta key: given to the Meta client only, never printed, logged or written
  createMeta?: AskDeps["createMeta"];
  print: (line: string) => void;
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
  random?: () => number;
};

export type Summary = {
  questions: number;
  asked: number;
  passed: number;
  failed: number;
  notAsked: number; // after a question whose spend wasn't ok, the run stops asking
  modelAnswers: number;
  plainLists: number; // model misses
  paused: number; // plain lists while model calls were paused (failures)
  spendStops: number; // questions after which the counter reached its stop, or couldn't be read
  spendErrors: number; // questions whose cost didn't reach the counter
  metaCalls: number;
  estUsd: string;
  ms: number[];
  // The run passes only when every question was asked and passed, every cost reached the counter below its stop,
  // and at least one answer came from the model (AK1 asks for real Muse Spark calls).
  ok: boolean;
};

const CONSOLE = ["log", "info", "warn", "error", "debug"] as const;

// Every console line while `work` runs, kept here and never printed: the handler's log lines stay out of stdout,
// and the harness reads the ones it needs from them.
async function captured<T>(work: (lines: string[]) => Promise<T>): Promise<T> {
  const lines: string[] = [];
  const saved = CONSOLE.map((method) => [method, console[method]] as const);
  for (const method of CONSOLE) {
    console[method] = (...args: unknown[]) => {
      lines.push(format(...args));
    };
  }
  try {
    return await work(lines);
  } finally {
    for (const [method, fn] of saved) console[method] = fn;
  }
}

function jsonLines(lines: string[]): Record<string, unknown>[] {
  return lines.flatMap((line) => {
    try {
      const parsed: unknown = JSON.parse(line);
      return typeof parsed === "object" && parsed !== null ? [parsed as Record<string, unknown>] : [];
    } catch {
      return [];
    }
  });
}

const count = (value: unknown): number => (typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : 0);
// The log line's fields kept for a failed question's diagnosis (spec §4.9): Meta's error status, the error's class
// name for a 500 (logAsk writes only the name), and the final turn's ending. Null when absent.
const metaStatus = (value: unknown): number | null => (typeof value === "number" ? value : null);
const loggedError = (value: unknown): string | null => (typeof value === "string" ? value : null);
const finalTurn = (value: unknown): string | null => (value === "ok" || value === "skipped" || value === "failed" ? value : null);

export function localDate(ms: number): string {
  const d = new Date(ms);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// The questions in order, each through askTyped once; every answer appended to the answers file as it comes. After a
// question whose spend wasn't ok (a spend_error or spend_stop line), the run stops asking: the handler has set the
// stack's model-calls switch on, but this run's own switch read stays cached for 30 s, so a later question could
// still pay Meta while the counter misses its cost (C736). The caller fails the run when `ok` is false.
export async function runHarness(o: HarnessOptions): Promise<Summary> {
  const out = answersPath(o.dataDir, o.date);
  const questions = loadQuestions();
  const fixture = loadPins();
  const geocodes = loadGeocodes();
  if (questions.some((q) => q.route !== "ask")) throw new Error("questions.json: the harness asks typed questions only");
  await checkSpend(o, questions.length);

  const now = o.now ?? Date.now;
  const key = o.key;
  const deps: AskDeps = {
    ddb: memoryLimits(),
    limitsTableName: o.limitsTableName,
    isStopped: createStopSwitch(o.ssm, STOP_PREFIX),
    nearbyPins: fixtureNearby(now, fixture, geocodes),
    inMetroManila,
    spots: SPOTS,
    geocoder: fixtureGeocoder(geocodes),
    modelKey: { get: async () => key, drop: () => {} },
    createMeta: o.createMeta ?? createMeta,
    spendDdb: o.spendDdb,
    ssm: o.ssm,
    stopParamPrefix: STOP_PREFIX,
    now,
    sleep: o.sleep ?? ((ms) => new Promise<void>((done) => setTimeout(done, ms))),
    random: o.random ?? Math.random,
  };

  mkdirSync(dirname(out), { recursive: true });
  const run = new Date(now()).toISOString();
  const summary: Summary = {
    questions: questions.length,
    asked: 0,
    passed: 0,
    failed: 0,
    notAsked: 0,
    modelAnswers: 0,
    plainLists: 0,
    paused: 0,
    spendStops: 0,
    spendErrors: 0,
    metaCalls: 0,
    estUsd: "0",
    ms: [],
    ok: false,
  };
  let input = 0;
  let output = 0;

  await captured(async (lines) => {
    for (const q of questions) {
      const body = JSON.stringify({ question: q.text, ...(q.here === "fixture" && { here: fixture.here }) });
      const started = now();
      const res = await askTyped({ body, device: DEVICE }, deps);
      const ms = now() - started;
      const logged = jsonLines(lines.splice(0));
      const line = logged.find((l) => l.msg === "ask") ?? {};
      const spend = logged.some((l) => l.msg === "spend_error") ? "error" : logged.some((l) => l.msg === "spend_stop") ? "stop" : "ok";

      const answer = res.statusCode === 200 ? (JSON.parse(res.body) as { answer: Answer }).answer : null;
      const checks = check(q, res.statusCode, ms, answer, geocodes);
      const pass = Object.values(checks).every((c) => c !== false);
      const tokens = { input: count(line.input_tokens), output: count(line.output_tokens), reasoning: count(line.reasoning_tokens) };
      input += tokens.input;
      output += tokens.output;
      summary.asked++;
      summary.ms.push(ms);
      summary.metaCalls += count(line.meta_calls);
      summary[pass ? "passed" : "failed"]++;
      if (answer?.source === "model") summary.modelAnswers++;
      if (answer?.source === "plain_list") summary.plainLists++;
      if (answer?.fallback === "model_calls_paused") summary.paused++;
      if (spend === "stop") summary.spendStops++;
      if (spend === "error") summary.spendErrors++;

      const record = {
        run,
        id: q.id,
        route: q.route,
        ms,
        status: res.statusCode,
        answer,
        checks,
        pass,
        source: answer?.source ?? null,
        fallback: answer?.fallback ?? null,
        meta_calls: count(line.meta_calls),
        meta_status: metaStatus(line.meta_status),
        error: loggedError(line.error),
        final: finalTurn(line.final),
        input_tokens: tokens.input,
        output_tokens: tokens.output,
        reasoning_tokens: tokens.reasoning,
        est_usd: costOf({ spark_input_tokens: tokens.input, spark_output_tokens: tokens.output }),
        spend,
      };
      appendFileSync(out, `${JSON.stringify(record)}\n`);
      if (spend !== "ok") break;
    }
  });

  summary.notAsked = summary.questions - summary.asked;
  summary.ok =
    summary.notAsked === 0 && summary.failed === 0 && summary.spendStops === 0 && summary.spendErrors === 0 && summary.modelAnswers > 0;
  summary.estUsd = costOf({ spark_input_tokens: input, spark_output_tokens: output });
  const sorted = [...summary.ms].sort((a, b) => a - b);
  const at = (i: number) => sorted[Math.max(0, Math.min(sorted.length - 1, i))] ?? 0;
  o.print(`ask-eval: ${summary.questions} questions, ${summary.asked} asked, ${summary.passed} passed, ${summary.failed} failed`);
  o.print(`ask-eval: ${summary.modelAnswers} model answers, ${summary.plainLists} plain lists (model misses), ${summary.paused} paused`);
  o.print(
    `ask-eval: ${summary.spendStops} spend stops, ${summary.spendErrors} spend errors, ${summary.notAsked} not asked (the run stops asking at the first)`,
  );
  o.print(`ask-eval: handler ms min ${at(0)}, median ${at(Math.floor((sorted.length - 1) / 2))}, max ${at(sorted.length - 1)}`);
  o.print(`ask-eval: ${summary.metaCalls} Meta calls, est. $${summary.estUsd}`);
  o.print(`ask-eval: run ${summary.ok ? "passed" : "failed"}`);
  return summary;
}
