// Ask Lusot's typed harness (Task 18; spec AK1, C728): its fixtures, its path guard, its spend guard, and a dry run of
// the 10 typed questions through the real handler with a fake Meta. No network, no AWS, no key: the spend counter and
// SSM are aws-sdk-client-mock instance mocks, the geocoder is the fixture one and the question limits are in memory.
// The question texts are read from questions.json and never written here.
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { GetParameterCommand, PutParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, GetCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import type { Response, ResponseCreateParamsNonStreaming } from "openai/resources/responses/responses";
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import { SPEND_STOP_PARAM } from "../../src/ask/handler";
import type { Meta, MetaCall } from "../../src/ask/meta";
import { SPOTS } from "../../src/ask/spots";
import { LEVELS } from "../../src/ask/tool";
import { inMetroManila } from "../../src/metroManila";
import { awsError } from "../awsError";
import {
  answersPath,
  fixturePins,
  HarnessRefused,
  type HarnessOptions,
  loadGeocodes,
  loadPins,
  loadQuestions,
  runHarness,
  spanOf,
  STOP_PREFIX,
} from "./harness";

const REPO = fileURLToPath(new URL("../../../../", import.meta.url));
const KEY = "dry-run-key-0000000000000000000000";
const KINDS = ["reports", "no_reports", "place_too_broad", "no_place", "lookup_unavailable", "outside_metro_manila", "no_location", "off_topic"];

// --- the mocks -------------------------------------------------------------------------------------------------

const spendDdb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ssm = new SSMClient({ region: "ap-southeast-1" });
const spendMock = mockClient(spendDdb);
const ssmMock = mockClient(ssm);

let dataDir: string;
let createMeta: Mock<NonNullable<HarnessOptions["createMeta"]>>;
let printed: string[];

function options(over: Partial<HarnessOptions> = {}): HarnessOptions {
  return {
    dataDir,
    date: "2026-10-31",
    limitsTableName: "limits",
    spendDdb,
    ssm,
    key: KEY,
    createMeta,
    print: (line) => printed.push(line),
    ...over,
  };
}

const seeded = (usd: number) => ({ Item: { pk: "spend#meta", micro_usd: Math.round(usd * 1_000_000), seeded: true } });

beforeEach(() => {
  dataDir = mkdtempSync(join(tmpdir(), "lusot-ask-eval-"));
  printed = [];
  spendMock.reset();
  ssmMock.reset();
  spendMock.on(GetCommand).resolves(seeded(3));
  spendMock.on(UpdateCommand).resolves({ Attributes: { micro_usd: 3_010_000 } });
  ssmMock.on(GetParameterCommand, { Name: SPEND_STOP_PARAM }).resolves({ Parameter: { Value: "60" } });
  ssmMock.on(GetParameterCommand, { Name: `${STOP_PREFIX}model-calls` }).resolves({ Parameter: { Value: "off" } });
  ssmMock.on(PutParameterCommand).resolves({});
  createMeta = vi.fn<NonNullable<HarnessOptions["createMeta"]>>(() => {
    throw new Error("the test scripted no Meta");
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  rmSync(dataDir, { recursive: true, force: true });
});

// --- the fixtures ----------------------------------------------------------------------------------------------

describe("the fixtures", () => {
  it("the fixtures load and every typed question has an expect", () => {
    const questions = loadQuestions();
    const { here, pins } = loadPins();
    const geocodes = loadGeocodes();

    expect(questions.map((q) => q.id)).toEqual(["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"]);
    for (const q of questions) {
      expect(q.route, q.id).toBe("ask");
      expect(typeof q.text === "string" && q.text.trim().length > 0 && q.text.length <= 300, q.id).toBe(true);
      expect(q.here === null || q.here === "fixture", q.id).toBe(true);
      expect(KINDS, q.id).toContain(q.expect.kind);
      expect(typeof q.expect.crossing, q.id).toBe("boolean");
      expect(["light", "heavy", "on_foot", null], q.id).toContain(q.expect.vehicle);
      const { placeSource, placeId } = q.expect;
      expect([undefined, null, "spots", "nominatim", "here"], q.id).toContain(placeSource);
      if (placeSource === "spots") expect(SPOTS.some((spot) => spot.id === placeId), q.id).toBe(true);
      else if (placeSource === "nominatim") expect(geocodes.some((g) => g.id === placeId), q.id).toBe(true);
      else expect(placeId, q.id).toBeUndefined();
      for (const id of q.expect.suggestions ?? []) expect(SPOTS.some((spot) => spot.id === id), q.id).toBe(true);
      if (q.expect.deepest !== undefined) expect(pins.some((pin) => pin.id === q.expect.deepest && pin.mode === "live"), q.id).toBe(true);
    }
    // Only T3 sends the fixture location (the brief's "here" column).
    expect(questions.filter((q) => q.here === "fixture").map((q) => q.id)).toEqual(["T3"]);

    // The location: inside Metro Manila, at the accuracy the route takes (spec §5.1).
    expect(inMetroManila(here.lat, here.lng)).toBe(true);
    expect(here.accuracyM).toBeLessThanOrEqual(100);

    // Every pin resolves to a point, with a level from the nine; a demo pin has its own date and its credit.
    expect(new Set(pins.map((pin) => pin.id)).size).toBe(pins.length);
    const placed = fixturePins(Date.parse("2026-10-31T02:00:00Z"));
    expect(placed).toHaveLength(pins.length);
    for (const pin of placed) {
      expect(LEVELS, pin.id).toContain(pin.level);
      expect(["PATV", "NPLV", "NPATV"], pin.id).toContain(pin.passability);
      expect(Number.isFinite(Date.parse(pin.capturedAt)), pin.id).toBe(true);
      if (pin.mode === "demo") expect([pin.credit, pin.place, pin.event].every((s) => typeof s === "string" && s !== ""), pin.id).toBe(true);
    }

    // The three Nominatim answers: T5's a point inside, T7's a 1,200 m street inside with no listed spot in its box,
    // T8's a town outside, far wider than 300 m (C733: inMetroManila comes first).
    const geocode = (id: string) => {
      const found = geocodes.find((g) => g.id === id);
      if (found === undefined) throw new Error(`geocodes.json has no ${id}`);
      return found;
    };
    const point = geocode("quezon-araneta");
    expect(inMetroManila(point.lat, point.lng)).toBe(true);
    expect(spanOf(point.box)).toBeLessThan(300);
    const street = geocode("maginhawa");
    expect(inMetroManila(street.lat, street.lng)).toBe(true);
    expect(Math.abs(spanOf(street.box) - 1200)).toBeLessThan(10);
    const { south, north, west, east } = street.box;
    expect(SPOTS.filter((s) => s.lat >= south && s.lat <= north && s.lng >= west && s.lng <= east)).toEqual([]);
    const town = geocode("san-pablo");
    expect(inMetroManila(town.lat, town.lng)).toBe(false);
    expect(spanOf(town.box)).toBeGreaterThan(300);
  });
});

// --- the path guard --------------------------------------------------------------------------------------------

describe("the output path", () => {
  it("the harness refuses a sealed path", async () => {
    for (const sealed of ["sealed", "Sealed", "SEALED.", "sealed ", "sealed::$INDEX_ALLOCATION"]) {
      expect(() => answersPath(join(dataDir, sealed, "x"), "2026-10-31"), sealed).toThrow(HarnessRefused);
      expect(() => answersPath(`C:\\data\\${sealed}\\x`, "2026-10-31"), sealed).toThrow(HarnessRefused);
    }
    // Its own date folder can't name one either.
    expect(() => answersPath(dataDir, "sealed")).toThrow(HarnessRefused);
    // Nor a data folder inside the repo, whose files git could pick up.
    expect(() => answersPath(join(REPO, "lusot-data"), "2026-10-31")).toThrow(HarnessRefused);
    expect(() => answersPath(REPO, "2026-10-31")).toThrow(HarnessRefused);
    expect(answersPath(dataDir, "2026-10-31")).toBe(join(dataDir, "ask", "2026-10-31", "answers.jsonl"));

    // The run refuses before any AWS read, any Meta client or any file.
    await expect(runHarness(options({ dataDir: join(dataDir, "sealed") }))).rejects.toThrow(HarnessRefused);
    expect(spendMock.calls()).toHaveLength(0);
    expect(ssmMock.calls()).toHaveLength(0);
    expect(createMeta).not.toHaveBeenCalled();
    expect(existsSync(join(dataDir, "sealed"))).toBe(false);
  });
});

// --- the spend guard (C527, C736) ------------------------------------------------------------------------------

describe("the spend guard", () => {
  it.each([
    ["the total is at the stop", () => spendMock.on(GetCommand).resolves(seeded(60))],
    ["the total is over the stop", () => spendMock.on(GetCommand).resolves(seeded(61))],
    // 10 questions × 3 turns × $0.042 (UNREPORTED_USAGE) = $1.26: from $58.75, the worst case reaches $60.01.
    ["10 worst-case questions would reach the stop", () => spendMock.on(GetCommand).resolves(seeded(58.75))],
    ["the counter isn't seeded", () => spendMock.on(GetCommand).resolves({ Item: { pk: "spend#meta", micro_usd: 1 } })],
    ["the counter can't be read", () => spendMock.on(GetCommand).rejects(awsError("AccessDeniedException", 400))],
    ["the stop can't be read", () => ssmMock.on(GetParameterCommand, { Name: SPEND_STOP_PARAM }).rejects(awsError("AccessDeniedException", 400))],
    ["the stop isn't a number", () => ssmMock.on(GetParameterCommand, { Name: SPEND_STOP_PARAM }).resolves({ Parameter: { Value: "sixty" } })],
  ])("the harness refuses to start when %s, before any Meta call", async (_name, setup) => {
    setup();

    const run = runHarness(options());

    await expect(run).rejects.toThrow(HarnessRefused);
    // The refusal names an AWS error by its name only: its message can hold an ARN.
    await expect(run).rejects.not.toThrow(/arn:/);
    expect(createMeta).not.toHaveBeenCalled();
    expect(spendMock.commandCalls(UpdateCommand)).toHaveLength(0);
    expect(ssmMock.commandCalls(PutParameterCommand)).toHaveLength(0);
    expect(existsSync(join(dataDir, "ask"))).toBe(false);
  });

  it("starts when 10 worst-case questions stay under the stop", async () => {
    spendMock.on(GetCommand).resolves(seeded(58.73));
    createMeta.mockImplementation(() => scriptedMeta());

    await expect(runHarness(options())).resolves.toMatchObject({ questions: 10 });
  });
});

// --- the dry run -----------------------------------------------------------------------------------------------

type Fixture = Record<string, unknown> & { output: Record<string, unknown>[] };
const metaFixture = (name: string): Fixture => JSON.parse(readFileSync(new URL(`../fixtures/meta/${name}.json`, import.meta.url), "utf8"));

// What a model that reads each question right would send: turn 1's get_reports arguments, or off_topic.
const READINGS: Record<string, Record<string, unknown> | "off_topic"> = {
  T1: { place: "España cor. Maceda", here: false, since_minutes: 180, kind: "depth", vehicle: "none" },
  T2: { place: "España", here: false, since_minutes: 180, kind: "crossing", vehicle: "light" },
  T3: { place: "", here: true, since_minutes: 180, kind: "depth", vehicle: "none" },
  T4: { place: "", here: true, since_minutes: 180, kind: "depth", vehicle: "none" },
  T5: { place: "Quezon Ave corner Araneta", here: false, since_minutes: 60, kind: "depth", vehicle: "none" },
  T6: { place: "Taft Avenue malapit sa PGH", here: false, since_minutes: 180, kind: "crossing", vehicle: "on_foot" },
  T7: { place: "Maginhawa Street", here: false, since_minutes: 180, kind: "depth", vehicle: "none" },
  T8: { place: "San Pablo, Laguna", here: false, since_minutes: 180, kind: "depth", vehicle: "none" },
  T9: { place: "Taft Avenue in front of PGH", here: false, since_minutes: 180, kind: "crossing", vehicle: "heavy" },
  T10: "off_topic",
};

function reply(name: "ask_call" | "ask_answer", content: string): Response {
  const fixture = metaFixture(name);
  if (name === "ask_call") fixture.output[1].arguments = content;
  else (fixture.output[1] as { content: { text: string }[] }).content[0].text = content;
  return fixture as unknown as Response;
}

// One question's Meta, as the handler's factory makes it. It finds the question by its text (the user message's
// second part, after the location line), answers turn 1 with READINGS' call, and the final turn by citing every live
// report the tool returned.
function scriptedMeta(): Meta {
  const ids = new Map(loadQuestions().map((q) => [q.text, q.id]));
  const calls: MetaCall[] = [];
  return {
    calls,
    async respond(body: ResponseCreateParamsNonStreaming) {
      calls.push({ model: "muse-spark-1.3", status: 200, ms: 0 });
      const items = body.input as unknown as Record<string, unknown>[];
      const question = (items[0].content as { text: string }[])[1].text;
      const reading = READINGS[ids.get(question) ?? ""];
      if (reading === undefined) throw new Error("the dry run has no reading for this question");
      const output = items.find((item) => item.type === "function_call_output");
      if (reading === "off_topic") return reply("ask_answer", JSON.stringify({ kind: "off_topic", vehicle: "none", cited: [] }));
      if (output === undefined) return reply("ask_call", JSON.stringify(reading));
      const result = JSON.parse(String(output.output)) as { reports: { ref: string }[] };
      const cited = result.reports.map((report) => report.ref);
      return reply("ask_answer", JSON.stringify({ kind: reading.kind, vehicle: reading.vehicle, cited }));
    },
  };
}

describe("the dry run", () => {
  it("the harness prints no answer text (a dry run with a fake Meta)", async () => {
    createMeta.mockImplementation((deps) => {
      expect(deps.key).toBe(KEY);
      return scriptedMeta();
    });
    const consoleCalls: unknown[][] = [];
    for (const method of ["log", "info", "warn", "error", "debug"] as const) {
      vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
        consoleCalls.push(args);
      });
    }

    const summary = await runHarness(options());

    // With a model that reads each question right, the fixtures give every expected answer.
    expect(summary).toMatchObject({ questions: 10, passed: 10, failed: 0, plainLists: 0, paused: 0, spendErrors: 0, metaCalls: 19 });
    expect(createMeta).toHaveBeenCalledTimes(10);
    const lines = readFileSync(answersPath(dataDir, "2026-10-31"), "utf8").trim().split("\n").map((line) => JSON.parse(line));
    expect(lines.map((line) => line.id)).toEqual(loadQuestions().map((q) => q.id));
    for (const line of lines) {
      expect(line, line.id).toMatchObject({ route: "ask", status: 200, pass: true, source: "model", spend: "ok" });
      expect(Object.keys(line).sort(), line.id).toEqual(
        ["answer", "checks", "est_usd", "fallback", "id", "input_tokens", "meta_calls", "ms", "output_tokens", "pass", "reasoning_tokens", "route", "run", "source", "spend", "status"].sort(),
      );
      expect(Object.values(line.checks).every((check) => check === true || check === null), line.id).toBe(true);
    }
    // T1's tokens are the two fixture turns' (ask_call, then ask_answer).
    expect(lines[0]).toMatchObject({ meta_calls: 2, input_tokens: 1285 + 1897, output_tokens: 445 + 320, reasoning_tokens: 307 + 287 });

    // Every question's cost went to the counter through the harness's spend client, under the source "ask".
    expect(spendMock.commandCalls(UpdateCommand)).toHaveLength(10);
    for (const call of spendMock.commandCalls(UpdateCommand)) expect(call.args[0].input.Key).toEqual({ pk: "spend#meta" });

    // Stdout holds the harness's own count and timing lines only: no question, no place, no pin, no log line.
    expect(consoleCalls).toEqual([]);
    expect(printed.length).toBeGreaterThan(0);
    const names = [...SPOTS.map((spot) => spot.name), ...loadGeocodes().map((g) => g.name)];
    for (const text of printed) {
      expect(text.startsWith("ask-eval: ")).toBe(true);
      expect(text).not.toMatch(/[{}"]/);
      for (const q of loadQuestions()) expect(text).not.toContain(q.text);
      for (const pin of loadPins().pins) expect(text).not.toContain(pin.id);
      for (const name of names) expect(text).not.toContain(name);
    }
  });

  it("counts a paused stack's plain lists as failures", async () => {
    ssmMock.on(GetParameterCommand, { Name: `${STOP_PREFIX}model-calls` }).resolves({ Parameter: { Value: "on" } });

    const summary = await runHarness(options());

    expect(summary).toMatchObject({ questions: 10, passed: 0, failed: 10, plainLists: 10, paused: 10, metaCalls: 0 });
    expect(createMeta).not.toHaveBeenCalled();
    expect(printed.some((line) => /\b10 paused\b/.test(line))).toBe(true);
  });
});
