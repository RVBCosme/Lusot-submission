// Ask Lusot's spoken run (Task 21; spec AK2, C729): the harness's voice mode, with a made-up manifest, a folder of tiny
// WAVs written here and a fake Meta whose transcribe returns a set transcript. No network, no AWS, no key, and none of
// Rene's private scripts: every text below is invented. questions.json stays typed only; a spoken question takes its
// expectations from the manifest alone.
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { GetParameterCommand, PutParameterCommand, SSMClient } from "@aws-sdk/client-ssm";
import { DynamoDBDocumentClient, GetCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { mockClient } from "aws-sdk-client-mock";
import type { Response, ResponseCreateParamsNonStreaming } from "openai/resources/responses/responses";
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import { SPEND_STOP_PARAM } from "../../src/ask/handler";
import { type Meta, type MetaCall, MetaError, TRANSCRIBE_MODEL } from "../../src/ask/meta";
import { awsError } from "../awsError";
import { HarnessRefused, type HarnessOptions, loadQuestions, runHarness, STOP_PREFIX, voiceFromEnv } from "./harness";

const KEY = "dry-run-key-0000000000000000000000";
// Invented words that must never reach stdout, an error message or a log: the manifest's script and notes, and the
// transcripts (the answers file keeps those, for review).
const SCRIPT = "INVENTED-SCRIPT-WORDS";
const NOTE = "INVENTED-NOTE-WORDS";
const TRANSCRIPTS = ["invented transcript uno", "invented transcript dos", "invented transcript tres"];

const spendDdb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: "ap-southeast-1" }));
const ssm = new SSMClient({ region: "ap-southeast-1" });
const spendMock = mockClient(spendDdb);
const ssmMock = mockClient(ssm);

let root: string; // holds the data folder, the voice folder and the manifest
let dataDir: string;
let voiceDir: string;
let manifest: string;
let createMeta: Mock<NonNullable<HarnessOptions["createMeta"]>>;
let printed: string[];

// 16 kHz mono 16-bit PCM of `seconds` seconds, as backend/api/src/ask/wav.ts checks it: a 44-byte header, then samples.
function wav(seconds: number): Buffer {
  const samples = Math.round(seconds * 16000);
  const data = Buffer.alloc(samples * 2);
  data.writeInt16LE(seconds * 100, 0); // makes each clip's bytes its own
  const header = Buffer.alloc(44);
  header.write("RIFF", 0, "ascii");
  header.writeUInt32LE(36 + data.length, 4);
  header.write("WAVEfmt ", 8, "ascii");
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20); // PCM
  header.writeUInt16LE(1, 22); // mono
  header.writeUInt32LE(16000, 24);
  header.writeUInt32LE(32000, 28); // byte rate
  header.writeUInt16LE(2, 32); // block align
  header.writeUInt16LE(16, 34); // bits
  header.write("data", 36, "ascii");
  header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
}

type Entry = Record<string, unknown>;
// Three invented spoken questions, built on the typed fixtures' places and pins: V1 is the España-Maceda spot (two live
// reports), V2 the fixture point (one report), V3 off topic.
const entries = (): Entry[] => [
  {
    id: "V1",
    wav: "v1.wav",
    text: SCRIPT,
    here: null,
    place_meant: NOTE,
    why: NOTE,
    expect: { kind: "reports", placeSource: "spots", placeId: "espana-maceda", crossing: false, vehicle: null, count: 2 },
    reviewed: true,
  },
  {
    id: "V2",
    wav: "v2.wav",
    text: SCRIPT,
    here: "fixture",
    place_meant: NOTE,
    why: NOTE,
    expect: { kind: "reports", placeSource: "here", crossing: false, vehicle: null, count: 1 },
    reviewed: true,
  },
  {
    id: "V3",
    wav: "v3.wav",
    text: SCRIPT,
    here: null,
    place_meant: NOTE,
    why: NOTE,
    expect: { kind: "off_topic", placeSource: null, crossing: false, vehicle: null },
    reviewed: true,
  },
];

function writeManifest(list: Entry[] = entries()): void {
  writeFileSync(manifest, JSON.stringify({ about: NOTE, reviewed_by: NOTE, scripts: list }));
}

function options(over: Partial<HarnessOptions> = {}): HarnessOptions {
  return {
    dataDir,
    date: "2026-11-02",
    limitsTableName: "limits",
    spendDdb,
    ssm,
    key: KEY,
    createMeta,
    voice: { dir: voiceDir, manifest },
    print: (line) => printed.push(line),
    ...over,
  };
}

const seeded = (usd: number) => ({ Item: { pk: "spend#meta", micro_usd: Math.round(usd * 1_000_000), seeded: true } });

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "lusot-ask-voice-"));
  dataDir = join(root, "data");
  voiceDir = join(root, "clips");
  manifest = join(root, "m12-scripts.json");
  mkdirSync(voiceDir);
  writeFileSync(join(voiceDir, "v1.wav"), wav(1));
  writeFileSync(join(voiceDir, "v2.wav"), wav(2));
  writeFileSync(join(voiceDir, "v3.wav"), wav(1.5));
  writeManifest();
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
  rmSync(root, { recursive: true, force: true });
});

// --- the fake Meta ---------------------------------------------------------------------------------------------

type Fixture = Record<string, unknown> & { output: Record<string, unknown>[] };
const metaFixture = (name: string): Fixture => JSON.parse(readFileSync(new URL(`../fixtures/meta/${name}.json`, import.meta.url), "utf8"));

function reply(name: "ask_call" | "ask_answer", content: string): Response {
  const fixture = metaFixture(name);
  if (name === "ask_call") fixture.output[1].arguments = content;
  else (fixture.output[1] as { content: { text: string }[] }).content[0].text = content;
  return fixture as unknown as Response;
}

// What a model that reads each invented transcript right would send.
const READINGS: Record<string, Record<string, unknown> | "off_topic"> = {
  [TRANSCRIPTS[0]]: { place: "España cor. Maceda", here: false, since_minutes: 180, kind: "depth", vehicle: "none" },
  [TRANSCRIPTS[1]]: { place: "", here: true, since_minutes: 180, kind: "depth", vehicle: "none" },
  [TRANSCRIPTS[2]]: "off_topic",
  // A place heard wrong: the speaker meant España-Maceda, and the transcript came out as another listed spot.
  "invented misheard": { place: "Taft Avenue in front of PGH", here: false, since_minutes: 180, kind: "depth", vehicle: "none" },
};

type Heard = { transcript: string; bytes: number }; // what the fake saw of each clip, for the test to check
function scriptedVoiceMeta(transcript: string, heard: Heard[] = [], failTranscription = false): Meta {
  const calls: MetaCall[] = [];
  return {
    calls,
    async transcribe(audio) {
      calls.push({ model: TRANSCRIBE_MODEL, status: failTranscription ? 503 : 200, ms: 0 });
      heard.push({ transcript, bytes: audio.length });
      if (failTranscription) throw new MetaError(503);
      return { transcript, audioDurationMs: null };
    },
    async respond(body: ResponseCreateParamsNonStreaming) {
      calls.push({ model: "muse-spark-1.3", status: 200, ms: 0 });
      const items = body.input as unknown as Record<string, unknown>[];
      const question = (items[0].content as { text: string }[])[1].text;
      const reading = READINGS[question];
      if (reading === undefined) throw new Error("the voice test has no reading for this transcript");
      const output = items.find((item) => item.type === "function_call_output");
      if (reading === "off_topic") return reply("ask_answer", JSON.stringify({ kind: "off_topic", vehicle: "none", cited: [] }));
      if (output === undefined) return reply("ask_call", JSON.stringify(reading));
      const result = JSON.parse(String(output.output)) as { reports: { ref: string }[] };
      return reply("ask_answer", JSON.stringify({ kind: reading.kind, vehicle: reading.vehicle, cited: result.reports.map((r) => r.ref) }));
    },
  };
}

// Question i gets TRANSCRIPTS[i], in order (the harness asks them in order, one Meta each).
function scriptMetas(heard: Heard[] = []): void {
  let next = 0;
  createMeta.mockImplementation(() => scriptedVoiceMeta(TRANSCRIPTS[next++], heard));
}

type Line = Record<string, unknown> & { id: string; checks: Record<string, boolean | null> };
const answerLines = (): Line[] =>
  readFileSync(join(dataDir, "ask", "2026-11-02", "answers.jsonl"), "utf8")
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));

function silenceConsole(): unknown[][] {
  const calls: unknown[][] = [];
  for (const method of ["log", "info", "warn", "error", "debug"] as const) {
    vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
      calls.push(args);
    });
  }
  return calls;
}

// --- the run ---------------------------------------------------------------------------------------------------

describe("the spoken run", () => {
  it("asks each clip through askVoice and passes when every answer is as the manifest expects", async () => {
    const heard: Heard[] = [];
    scriptMetas(heard);
    const consoleCalls = silenceConsole();

    const summary = await runHarness(options());

    expect(summary).toMatchObject({
      questions: 3,
      asked: 3,
      passed: 3,
      failed: 0,
      notAsked: 0,
      modelAnswers: 3,
      plainLists: 0,
      spendStops: 0,
      spendErrors: 0,
      placesHeard: 3,
      ok: true,
    });
    expect(createMeta).toHaveBeenCalledTimes(3);
    // The clips reached Meta's transcription as the files hold them (1 s, 2 s and 1.5 s of 16 kHz 16-bit audio).
    expect(heard.map((h) => h.bytes)).toEqual([44 + 32000, 44 + 64000, 44 + 48000]);

    const lines = answerLines();
    expect(lines.map((line) => line.id)).toEqual(["V1", "V2", "V3"]);
    for (const [i, line] of lines.entries()) {
      expect(line, line.id).toMatchObject({ route: "ask_voice", status: 200, pass: true, source: "model", spend: "ok", transcript: TRANSCRIPTS[i] });
      expect(Object.values(line.checks).every((c) => c === true || c === null), line.id).toBe(true);
    }
    // The typed record's fields, plus the transcript (review only) and the clip's and transcription's timings.
    expect(Object.keys(lines[0]).sort()).toEqual(
      [
        "answer", "at", "audio_ms", "checks", "error", "est_usd", "fallback", "final", "id", "input_tokens", "meta_calls", "meta_status", "ms",
        "output_tokens", "pass", "reasoning_tokens", "route", "run", "source", "spend", "status", "transcribe_ms", "transcript",
      ].sort(),
    );
    expect(lines[0]).toMatchObject({ audio_ms: 1000 });
    expect(lines[2]).toMatchObject({ audio_ms: 1500, final: null });
    expect(lines[0].answer).toMatchObject({ kind: "reports", count: 2, place: { source: "spots" } });
    expect(lines[1].answer).toMatchObject({ kind: "reports", count: 1, place: { source: "here" } });

    // Counts and timings only on stdout: never a transcript, an answer, a place, or the script's own words.
    expect(consoleCalls).toEqual([]);
    expect(printed).toContain("ask-eval: spoken questions, synthetic clips (spec C729)");
    expect(printed).toContain("ask-eval: places heard right 3 of 3 (synthetic clips)");
    expect(printed.at(-1)).toBe("ask-eval: run passed");
    for (const text of printed) {
      expect(text.startsWith("ask-eval: ")).toBe(true);
      expect(text).not.toMatch(/[{}"]/);
      for (const secret of [SCRIPT, NOTE, ...TRANSCRIPTS, "Maceda", "España"]) expect(text).not.toContain(secret);
    }
    // The manifest's script and notes are in no record.
    expect(readFileSync(join(dataDir, "ask", "2026-11-02", "answers.jsonl"), "utf8")).not.toMatch(new RegExp(`${SCRIPT}|${NOTE}`));
    // Every question's cost went to the counter under the spend source, as the typed run's does.
    expect(spendMock.commandCalls(UpdateCommand)).toHaveLength(3);
  });

  it("sends the fixture point only with a clip whose entry says so", async () => {
    scriptMetas();
    const list = entries();
    // V2 says it was asked without a location, and the model asks for "here": no_location, as the typed T4.
    list[1].here = null;
    list[1].expect = { kind: "no_location", placeSource: null, crossing: false, vehicle: null };
    writeManifest(list);

    const summary = await runHarness(options());

    expect(summary).toMatchObject({ passed: 3, failed: 0 });
    expect(answerLines()[1].answer).toMatchObject({ kind: "no_location", place: null });
  });

  it("counts a place heard wrong as a failed check and as a place not heard right", async () => {
    let next = 0;
    // V1's clip comes out as another listed spot.
    createMeta.mockImplementation(() => scriptedVoiceMeta(["invented misheard", TRANSCRIPTS[1], TRANSCRIPTS[2]][next++]));

    const summary = await runHarness(options());

    expect(summary).toMatchObject({ asked: 3, passed: 2, failed: 1, placesHeard: 2, ok: false });
    expect(answerLines()[0]).toMatchObject({ id: "V1", pass: false, checks: { place: false } });
    expect(printed).toContain("ask-eval: places heard right 2 of 3 (synthetic clips)");
    expect(printed.at(-1)).toBe("ask-eval: run failed");
  });

  it("fails a spoken question whose count differs from the manifest's", async () => {
    scriptMetas();
    const list = entries();
    // The fixtures give V1's spot two live reports; the manifest says three.
    list[0].expect = { kind: "reports", placeSource: "spots", placeId: "espana-maceda", crossing: false, vehicle: null, count: 3 };
    writeManifest(list);

    const summary = await runHarness(options());

    expect(summary).toMatchObject({ asked: 3, passed: 2, failed: 1, placesHeard: 3 });
    expect(answerLines()[0]).toMatchObject({ id: "V1", pass: false, checks: { place: true, kind: true, count: false } });
    expect(answerLines()[0].answer).toMatchObject({ count: 2 });
  });

  it("saves when each answer arrived, the time the app renders its cards at", async () => {
    // Fixture pins are placed while the question runs, so a card's age is right only at the answer's arrival.
    let t = Date.parse("2026-11-02T02:00:00Z");
    let next = 0;
    createMeta.mockImplementation(() => {
      const meta = scriptedVoiceMeta(TRANSCRIPTS[next++], []);
      const transcribe = meta.transcribe.bind(meta);
      meta.transcribe = async (...args: Parameters<typeof transcribe>) => {
        t += 1000; // the transcription takes a second, inside the handler's 4 s budget
        return transcribe(...args);
      };
      return meta;
    });

    await runHarness(options({ now: () => t }));

    const [first] = answerLines();
    expect(Date.parse(String(first.at)) - Date.parse(String(first.run))).toBeGreaterThanOrEqual(1000);
  });

  it("saves a later time for each later question", async () => {
    scriptMetas();
    let ticks = Date.parse("2026-11-02T02:00:00Z");
    const now = () => ++ticks; // 1 ms for every read of the clock, so each question starts later than the one before

    await runHarness(options({ now }));

    const lines = answerLines();
    const times = lines.map((line) => Date.parse(String(line.at)));
    expect(times.every(Number.isFinite)).toBe(true);
    expect(String(lines[0].at)).toMatch(/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/);
    const run = Date.parse(String(lines[0].run));
    expect(times[0]).toBeGreaterThan(run);
    expect(times[1]).toBeGreaterThan(times[0]);
    expect(times[2]).toBeGreaterThan(times[1]);
  });

  it("judges a question with no place by its kind: heard right when the kind is the expected one", async () => {
    scriptMetas();
    const list = entries();
    // V3 is off topic with no place; expecting another kind makes it a miss on both counts.
    list[2].expect = { kind: "no_reports", placeSource: null, crossing: false, vehicle: null };
    writeManifest(list);

    const summary = await runHarness(options());

    expect(summary).toMatchObject({ passed: 2, failed: 1, placesHeard: 2 });
  });

  it("a stack with model calls paused refuses every spoken question, which fails the run", async () => {
    ssmMock.on(GetParameterCommand, { Name: `${STOP_PREFIX}model-calls` }).resolves({ Parameter: { Value: "on" } });

    const summary = await runHarness(options());

    expect(createMeta).not.toHaveBeenCalled();
    expect(summary).toMatchObject({ questions: 3, asked: 3, passed: 0, failed: 3, modelAnswers: 0, placesHeard: 0, ok: false });
    expect(answerLines()[0]).toMatchObject({ id: "V1", status: 503, answer: null, pass: false, transcript: null });
  });

  it("a transcription that fails fails that question, and the run goes on", async () => {
    let next = 0;
    createMeta.mockImplementation(() => scriptedVoiceMeta(TRANSCRIPTS[next++], [], next === 1));

    const summary = await runHarness(options());

    expect(summary).toMatchObject({ asked: 3, passed: 2, failed: 1, placesHeard: 2, ok: false });
    expect(answerLines()[0]).toMatchObject({ id: "V1", status: 503, answer: null, pass: false, transcript: null, audio_ms: 1000 });
  });

  // C736, as the typed run has it: after a question whose spend isn't ok, the run stops asking.
  it("stops asking after a spoken question whose spend isn't ok", async () => {
    spendMock.on(UpdateCommand).rejects(awsError("ProvisionedThroughputExceededException", 400));
    scriptMetas();

    const summary = await runHarness(options());

    expect(createMeta).toHaveBeenCalledTimes(1);
    expect(summary).toMatchObject({ questions: 3, asked: 1, notAsked: 2, spendErrors: 1, ok: false });
    expect(answerLines()).toHaveLength(1);
    expect(ssmMock.commandCalls(PutParameterCommand).map((call) => call.args[0].input)).toEqual([
      expect.objectContaining({ Name: `${STOP_PREFIX}model-calls`, Value: "on" }),
    ]);
  });
});

// --- the refusals: all before any AWS read, any Meta client or any answers file --------------------------------

function expectNothingStarted(): void {
  expect(spendMock.calls()).toHaveLength(0);
  expect(ssmMock.calls()).toHaveLength(0);
  expect(createMeta).not.toHaveBeenCalled();
  expect(existsSync(join(dataDir, "ask"))).toBe(false);
}

async function refusal(over: Partial<HarnessOptions> = {}): Promise<Error> {
  const error = await runHarness(options(over)).then(
    () => undefined,
    (err: unknown) => err,
  );
  expect(error).toBeInstanceOf(HarnessRefused);
  const message = (error as Error).message;
  for (const secret of [SCRIPT, NOTE, ...TRANSCRIPTS, "arn:"]) expect(message).not.toContain(secret);
  expectNothingStarted();
  return error as Error;
}

describe("the spoken run's refusals", () => {
  it("refuses a manifest with an entry that isn't reviewed, naming the count", async () => {
    const list = entries();
    list[1].reviewed = false;
    delete list[2].reviewed;
    writeManifest(list);

    expect((await refusal()).message).toMatch(/2 of 3 .*not reviewed/);
  });

  it.each([
    ["reviewed is the string true", (e: Entry) => (e.reviewed = "true")],
    ["its clip's name is a path", (e: Entry) => (e.wav = "..\\outside.wav")],
    ["its clip's name has a folder", (e: Entry) => (e.wav = "sub/v1.wav")],
    ["its clip isn't a .wav name", (e: Entry) => (e.wav = "v1.mp3")],
    ["its id is empty", (e: Entry) => (e.id = "")],
    ["its here is neither fixture nor null", (e: Entry) => (e.here = "somewhere")],
    ["its kind isn't one the app words", (e: Entry) => (e.expect = { kind: "mystery", crossing: false, vehicle: null })],
    ["its crossing isn't a boolean", (e: Entry) => (e.expect = { kind: "reports", crossing: "no", vehicle: null })],
    ["its vehicle is unknown", (e: Entry) => (e.expect = { kind: "reports", crossing: false, vehicle: "tank" })],
    ["its spot id isn't in spots.json", (e: Entry) => (e.expect = { kind: "reports", placeSource: "spots", placeId: "no-such-spot", crossing: false, vehicle: null })],
    ["its geocode id isn't in geocodes.json", (e: Entry) => (e.expect = { kind: "reports", placeSource: "nominatim", placeId: "no-such-geocode", crossing: false, vehicle: null })],
    ["its count isn't a whole number", (e: Entry) => (e.expect = { kind: "reports", crossing: false, vehicle: null, count: 1.5 })],
  ])("refuses a manifest whose first entry has %s", async (_name, change) => {
    const list = entries();
    change(list[0]);
    writeManifest(list);

    await refusal();
  });

  it("refuses a manifest that isn't JSON, or has no entries, without quoting it", async () => {
    writeFileSync(manifest, `{ ${SCRIPT} `);
    await refusal();
    writeFileSync(manifest, JSON.stringify({ scripts: [] }));
    await refusal();
    writeFileSync(manifest, JSON.stringify({ about: NOTE }));
    await refusal();
  });

  it("refuses a manifest it can't find", async () => {
    await refusal({ voice: { dir: voiceDir, manifest: join(root, "nope.json") } });
  });

  it("refuses a missing clip, naming the entry and not the file", async () => {
    rmSync(join(voiceDir, "v2.wav"));

    const error = await refusal();

    expect(error.message).toContain("V2");
    expect(error.message).not.toContain("v2.wav");
  });

  it("refuses a clip that isn't a WAV the handler accepts, before it can cost anything", async () => {
    writeFileSync(join(voiceDir, "v3.wav"), Buffer.from("not a wav"));
    expect((await refusal()).message).toContain("V3");
    writeFileSync(join(voiceDir, "v3.wav"), wav(0.2)); // under the handler's 0.5 s
    expect((await refusal()).message).toContain("V3");
  });

  it("refuses when the spoken run's worst case, clips included, would reach the spend stop", async () => {
    // Three questions at $0.126 worst case is $0.378, which from $59.6215 stays under $60. The clips' whole seconds
    // (1 + 2 + 2) billed on 3 tries each add $0.00075, which reaches $60.00025.
    spendMock.on(GetCommand).resolves(seeded(59.6215));

    await expect(runHarness(options())).rejects.toThrow(HarnessRefused);
    expect(createMeta).not.toHaveBeenCalled();
    expect(existsSync(join(dataDir, "ask"))).toBe(false);

    spendMock.on(GetCommand).resolves(seeded(59.62));
    scriptMetas();
    await expect(runHarness(options())).resolves.toMatchObject({ asked: 3 });
  });

  // Neither folder exists, so without its guard each path would still be refused, as unreadable. The message is what
  // proves the sealed rule did it: each half names its own path and the rule.
  it("refuses a voice folder or a manifest path with a part named sealed, in every spelling, by the sealed rule", async () => {
    for (const sealed of ["sealed", "Sealed", "SEALED.", "sealed ", "sealed::$INDEX_ALLOCATION"]) {
      const folder = await refusal({ voice: { dir: join(root, sealed, "clips"), manifest } });
      expect(folder.message, sealed).toBe("refused: the voice folder is inside a folder named sealed");
      const file = await refusal({ voice: { dir: voiceDir, manifest: join(root, sealed, "m12-scripts.json") } });
      expect(file.message, sealed).toBe("refused: the voice manifest is inside a folder named sealed");
    }
  });

  it("refuses a manifest entry's expect with a key the checks don't read, naming the entry and the key only", async () => {
    const list = entries();
    list[1].expect = { kind: "reports", placeSource: "here", crossing: false, vehicle: null, coutn: 1 };
    writeManifest(list);

    const error = await refusal();

    expect(error.message).toBe("refused: voice manifest entry V2 has an unknown key in expect: coutn");
  });

  it("names an unknown key only when it is a plain word, so no text of the manifest is echoed", async () => {
    const list = entries();
    list[0].expect = { kind: "reports", crossing: false, vehicle: null, [`${NOTE} with spaces`]: 1 };
    writeManifest(list);

    const error = await refusal();

    expect(error.message).toBe("refused: voice manifest entry V1 has an unknown key in expect: (not a plain word)");
  });

  it("reads a manifest that starts with a UTF-8 byte order mark, as Windows PowerShell writes one", async () => {
    scriptMetas();
    // The three bytes EF BB BF, written as bytes, before the JSON.
    writeFileSync(manifest, Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), readFileSync(manifest)]));

    await expect(runHarness(options())).resolves.toMatchObject({ asked: 3, passed: 3 });
  });
});

// --- the environment -------------------------------------------------------------------------------------------

describe("voiceFromEnv", () => {
  it("is off without LUSOT_ASK_VOICE_DIR, so the typed set runs", () => {
    expect(voiceFromEnv({}, "C:\\data")).toBeUndefined();
    expect(voiceFromEnv({ LUSOT_ASK_VOICE_DIR: "" }, "C:\\data")).toBeUndefined();
  });

  it("takes the folder, and the manifest from LUSOT_ASK_VOICE_MANIFEST or <data>\\voice\\m12-scripts.json", () => {
    expect(voiceFromEnv({ LUSOT_ASK_VOICE_DIR: "D:\\clips" }, "C:\\data")).toEqual({ dir: "D:\\clips", manifest: join("C:\\data", "voice", "m12-scripts.json") });
    expect(voiceFromEnv({ LUSOT_ASK_VOICE_DIR: "D:\\clips", LUSOT_ASK_VOICE_MANIFEST: "D:\\x\\m.json" }, "C:\\data")).toEqual({
      dir: "D:\\clips",
      manifest: "D:\\x\\m.json",
    });
  });
});

describe("questions.json", () => {
  it("stays typed only: a spoken question's expectations are in the private manifest, never in the repo", () => {
    expect(loadQuestions().every((q) => q.route === "ask")).toBe(true);
    expect(loadQuestions().some((q) => "wav" in q)).toBe(false);
  });
});
