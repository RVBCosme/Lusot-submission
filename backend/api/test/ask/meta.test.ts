// The fixtures in test/fixtures/meta/ take their shapes and numbers from Task 2's probe (Oct 30; its saved calls
// in the private data folder): ask_call.json from a `low` turn 1 that called get_reports, ask_answer.json from
// the turn that answered it, and ask_offtopic.json from the off-topic question. The probe saved each call's
// status, token counts, tool arguments and answer, not the raw body, so the envelope follows Meta's Responses
// schema (dev.meta.ai/docs/api-reference/responses/schemas), and every id, call_id and encrypted_content is a
// placeholder. The probe had no incomplete response, so ask_incomplete.json is written by hand. transcribe.json takes
// MS1's shape (backend/analysis's fixture, the example on dev.meta.ai/docs/speech-to-text), with its own words.
import { readFileSync } from "node:fs";
import type { ResponseCreateParamsNonStreaming } from "openai/resources/responses/responses";
import { afterEach, beforeEach, describe, expect, it, type MockInstance, vi } from "vitest";
import { BUDGET, Deadline } from "../../src/ask/deadline";
import { createMeta, type MetaDeps, MetaError } from "../../src/ask/meta";

const START = Date.parse("2026-10-30T10:00:00Z"); // a whole second, so an HTTP date can name it exactly
const KEY = "sentinel-model-key-00000000000000000000";
const QUESTION = "Gaano kataas ang tubig sa Sentinel Street ngayon?";
const ANSWER = "sentinel-answer-text";

type Fixture = Record<string, unknown> & { output: Record<string, unknown>[] };
const fixture = (name: string): Fixture =>
  JSON.parse(readFileSync(new URL(`../fixtures/meta/${name}.json`, import.meta.url), "utf8"));

type Reply = { status: number; body: unknown; headers?: Record<string, string> };
// A transcription's body is a form, kept as it was sent; a Responses body is JSON, kept parsed.
type Sent = { url: string; method: string | undefined; headers: Headers; body: Record<string, unknown>; form?: FormData };

let clock: number; // the fake clock that sleep, now and the retry tests' Deadline read
let sleeps: number[];
let sent: Sent[];
let replies: (Reply | ((init: RequestInit) => Promise<Response>))[];
let errorSpy: MockInstance<typeof console.error>;
let logSpy: MockInstance<typeof console.log>;
let warnSpy: MockInstance<typeof console.warn>;
let infoSpy: MockInstance<typeof console.info>;
let debugSpy: MockInstance<typeof console.debug>;

const logged = () =>
  [errorSpy, logSpy, warnSpy, infoSpy, debugSpy].flatMap((spy) => spy.mock.calls.map((args) => args.map(String).join(" ")));

const fetchFn = (async (input: string | URL | Request, init?: RequestInit) => {
  const form = init?.body instanceof FormData ? init.body : undefined;
  sent.push({
    url: String(input),
    method: init?.method,
    headers: new Headers(init?.headers),
    body: form === undefined ? JSON.parse(String(init?.body)) : {},
    form,
  });
  const next = replies.shift();
  if (next === undefined) throw new Error("the test gave no reply for this call");
  if (typeof next === "function") return next(init ?? {});
  return new Response(JSON.stringify(next.body), {
    status: next.status,
    headers: { "content-type": "application/json", ...next.headers },
  });
}) as typeof fetch;

const ok = (name: string): Reply => ({ status: 200, body: fixture(name) });
const fail = (status: number, headers?: Record<string, string>): Reply => ({
  status,
  body: { error: { message: `error ${status}`, type: "error", code: String(status) } },
  headers,
});

function deps(over: Partial<MetaDeps> = {}): MetaDeps {
  return {
    key: KEY,
    fetchFn,
    sleep: async (ms) => {
      sleeps.push(ms);
      clock += ms;
    },
    random: () => 0.5,
    now: () => clock,
    ...over,
  };
}

// A Deadline whose model mark is `leftMs` away on the fake clock.
const deadline = (leftMs: number = BUDGET.modelBy) => new Deadline(clock - (BUDGET.modelBy - leftMs), () => clock);

const body = (over: Partial<ResponseCreateParamsNonStreaming> = {}): ResponseCreateParamsNonStreaming => ({
  model: "muse-spark-1.3",
  input: QUESTION,
  ...over,
});

async function failure(promise: Promise<unknown>): Promise<MetaError> {
  const err = await promise.then(
    () => undefined,
    (e: unknown) => e,
  );
  expect(err).toBeInstanceOf(MetaError);
  return err as MetaError;
}

beforeEach(() => {
  clock = START;
  sleeps = [];
  sent = [];
  replies = [];
  errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
  warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
  debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("the model", () => {
  it("only muse-spark-1.3 is allowed", async () => {
    replies = [ok("ask_call")];
    const meta = createMeta(deps());

    await meta.respond(body(), deadline(), BUDGET.modelBy);

    expect(sent).toHaveLength(1);
    expect(sent[0].body.model).toBe("muse-spark-1.3");
  });

  it.each(["muse-spark-1.3-contributor", "muse-voice-transcribe-1.0", "gpt-4o"])(
    "%s is refused before any call",
    async (model) => {
      const meta = createMeta(deps());

      await expect(meta.respond(body({ model }), deadline(), BUDGET.modelBy)).rejects.toThrow(/only muse-spark-1\.3/);
      expect(sent).toHaveLength(0);
      expect(meta.calls).toEqual([]);
    },
  );
});

describe("the request", () => {
  it("every responses body sends store false, even when the caller sets store true", async () => {
    replies = [ok("ask_call"), ok("ask_call")];
    const meta = createMeta(deps());

    await meta.respond(body({ store: true }), deadline(), BUDGET.modelBy);
    await meta.respond(body(), deadline(), BUDGET.modelBy);

    expect(sent.map((s) => s.body.store)).toEqual([false, false]);
    expect(sent[0].body.input).toBe(QUESTION);
  });

  it("goes to Meta's Responses endpoint with the key as a bearer token", async () => {
    replies = [ok("ask_call")];

    await createMeta(deps()).respond(body(), deadline(), BUDGET.modelBy);

    expect(sent[0].url).toBe("https://api.meta.ai/v1/responses");
    expect(sent[0].method).toBe("POST");
    expect(sent[0].headers.get("authorization")).toBe(`Bearer ${KEY}`);
  });
});

describe("the answer", () => {
  it("a 200 gives the SDK's Response, with the answer as its output text", async () => {
    replies = [ok("ask_answer")];
    const meta = createMeta(deps());

    const response = await meta.respond(body(), deadline(), BUDGET.modelBy);

    expect(response.status).toBe("completed");
    expect(JSON.parse(response.output_text)).toEqual({ kind: "depth", vehicle: "none", cited: ["r1", "r2"] });
    expect(meta.calls).toEqual([{ model: "muse-spark-1.3", status: 200, ms: 0 }]);
  });

  it("a function call comes back with its reasoning item for the next turn", async () => {
    replies = [ok("ask_call")];

    const response = await createMeta(deps()).respond(body(), deadline(), BUDGET.modelBy);

    expect(response.output.map((item) => item.type)).toEqual(["reasoning", "function_call"]);
    const call = response.output[1];
    expect(call.type === "function_call" && call.call_id).toBe("call_fixture_1");
    expect(response.output_text).toBe("");
  });

  it("an off-topic answer and an incomplete response come back as they are, for the turns to judge", async () => {
    replies = [ok("ask_offtopic"), ok("ask_incomplete")];
    const meta = createMeta(deps());

    const offTopic = await meta.respond(body(), deadline(), BUDGET.modelBy);
    const incomplete = await meta.respond(body(), deadline(), BUDGET.modelBy);

    expect(JSON.parse(offTopic.output_text).kind).toBe("off_topic");
    expect(incomplete.status).toBe("incomplete");
    expect(incomplete.incomplete_details?.reason).toBe("max_output_tokens");
    expect(sent).toHaveLength(2);
  });
});

describe("retries", () => {
  it("a 429 then a 200 makes two calls", async () => {
    replies = [fail(429), ok("ask_call")];
    const meta = createMeta(deps());

    await meta.respond(body(), deadline(), BUDGET.modelBy);

    expect(sent).toHaveLength(2);
    expect(sleeps).toEqual([1000]); // 500 ms plus half of the 1,000 ms jitter
    expect(meta.calls.map((c) => c.status)).toEqual([429, 200]);
  });

  it.each([429, 500, 503])("a %i is tried at most 3 times, waiting 500 ms and then 1,000 ms, plus jitter", async (status) => {
    replies = [fail(status), fail(status), fail(status)];
    const meta = createMeta(deps({ random: () => 0.25 }));

    const err = await failure(meta.respond(body(), deadline(), BUDGET.modelBy));

    expect(err.status).toBe(status);
    expect(sent).toHaveLength(3); // the SDK makes no retries of its own
    expect(sleeps).toEqual([750, 1250]);
    expect(meta.calls.map((c) => c.status)).toEqual([status, status, status]);
  });

  it("Retry-After sets the wait when it is longer, in seconds or as an HTTP date", async () => {
    replies = [
      fail(503, { "retry-after": "2" }),
      ok("ask_call"),
      fail(429, { "retry-after": new Date(START + 2000 + 3000).toUTCString() }),
      ok("ask_call"),
      fail(429, { "retry-after": "0" }),
      ok("ask_call"),
    ];
    const meta = createMeta(deps());

    await meta.respond(body(), deadline(), BUDGET.modelBy);
    await meta.respond(body(), deadline(), BUDGET.modelBy);
    await meta.respond(body(), deadline(), BUDGET.modelBy);

    expect(sleeps).toEqual([2000, 3000, 1000]);
  });

  it("Retry-After past the deadline means no retry", async () => {
    replies = [fail(503, { "retry-after": "60" })];
    const meta = createMeta(deps());

    const err = await failure(meta.respond(body(), deadline(3000), BUDGET.modelBy));

    expect(err.status).toBe(503);
    expect(sent).toHaveLength(1);
    expect(sleeps).toEqual([]);
  });

  it("a backoff that would end past the mark isn't taken", async () => {
    replies = [fail(429)];
    const meta = createMeta(deps({ random: () => 0.9 }));

    const err = await failure(meta.respond(body(), deadline(1200), BUDGET.modelBy)); // a 1,400 ms wait

    expect(err.status).toBe(429);
    expect(sent).toHaveLength(1);
    expect(sleeps).toEqual([]);
  });

  // A retry needs 1,500 ms (MIN_TRY_MS) left before the mark once its wait ends. random 0.5 makes a 1,000 ms wait.
  it("503 then a retry with too little time left: one call and MetaError(503)", async () => {
    replies = [fail(503), ok("ask_call")];
    const meta = createMeta(deps());

    const err = await failure(meta.respond(body(), deadline(2499), BUDGET.modelBy)); // 1,499 ms left after the wait

    expect(err.status).toBe(503);
    expect(sent).toHaveLength(1);
    expect(sleeps).toEqual([]);
    expect(meta.calls.map((c) => c.status)).toEqual([503]);
  });

  it("exactly 1,500 ms left after the wait still retries", async () => {
    replies = [fail(503), ok("ask_call")];
    const meta = createMeta(deps());

    await meta.respond(body(), deadline(2500), BUDGET.modelBy);

    expect(sent).toHaveLength(2);
    expect(sleeps).toEqual([1000]);
    expect(meta.calls.map((c) => c.status)).toEqual([503, 200]);
  });

  it.each([
    { statuses: [429, 503], leftMs: 3900, thrown: 503 }, // the 503's 1,500 ms wait would leave 1,400 ms
    { statuses: [429, 503, 500], leftMs: BUDGET.modelBy, thrown: 500 },
  ])("tries that fail with $statuses throw the last try's status, $thrown", async ({ statuses, leftMs, thrown }) => {
    replies = statuses.map((status) => fail(status));
    const meta = createMeta(deps());

    const err = await failure(meta.respond(body(), deadline(leftMs), BUDGET.modelBy));

    expect(err.status).toBe(thrown);
    expect(meta.calls.map((c) => c.status)).toEqual(statuses);
  });

  it.each([400, 504])("a %i isn't retried", async (status) => {
    replies = [fail(status)];
    const meta = createMeta(deps());

    const err = await failure(meta.respond(body(), deadline(), BUDGET.modelBy));

    expect(err.status).toBe(status);
    expect(sent).toHaveLength(1);
    expect(sleeps).toEqual([]);
  });

  it.each([401, 402, 403])("a %i throws with its status, once", async (status) => {
    replies = [fail(status)];
    const meta = createMeta(deps());

    const err = await failure(meta.respond(body(), deadline(), BUDGET.modelBy));

    expect(err.status).toBe(status);
    expect(sent).toHaveLength(1);
    expect(meta.calls).toEqual([{ model: "muse-spark-1.3", status, ms: 0 }]);
  });

  it("a lost connection is MetaError(null), and isn't retried", async () => {
    replies = [() => Promise.reject(new TypeError("fetch failed"))];
    const meta = createMeta(deps());

    const err = await failure(meta.respond(body(), deadline(), BUDGET.modelBy));

    expect(err.status).toBeNull();
    expect(sent).toHaveLength(1);
    expect(meta.calls).toEqual([{ model: "muse-spark-1.3", status: null, ms: 0 }]);
  });
});

describe("the deadline", () => {
  it("the deadline aborts a call in flight: MetaError(null)", async () => {
    // Real time here: the mark is 50 ms away, and the call never answers on its own.
    const realStart = Date.now();
    replies = [
      (init) =>
        new Promise<Response>((_, reject) => {
          init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        }),
    ];
    const meta = createMeta(deps({ now: Date.now }));

    const err = await failure(meta.respond(body(), new Deadline(realStart, Date.now), 50));

    expect(err.status).toBeNull();
    expect(Date.now() - realStart).toBeGreaterThanOrEqual(45);
    expect(sent).toHaveLength(1);
    expect(meta.calls.map((c) => c.status)).toEqual([null]);
  });

  it("a mark already past sends nothing", async () => {
    const meta = createMeta(deps());

    const err = await failure(meta.respond(body(), deadline(0), BUDGET.modelBy));

    expect(err.status).toBeNull();
    expect(sent).toHaveLength(0);
    expect(meta.calls).toEqual([]);
  });
});

describe("what it keeps", () => {
  it("no log line, error or call record holds the key, the question or the answer", async () => {
    const answer = fixture("ask_answer");
    (answer.output[1].content as { text: string }[])[0].text = ANSWER;
    // A rejected key's message can echo the key, so this one does.
    const rejected: Reply = { status: 401, body: { error: { message: `bad key ${KEY} for ${QUESTION}`, type: "auth" } } };
    replies = [
      { status: 200, body: answer },
      rejected,
      fail(429),
      { status: 200, body: answer },
      () => Promise.reject(new TypeError(`fetch failed for ${KEY}`)),
    ];
    const meta = createMeta(deps());
    const errors: unknown[] = [];

    const response = await meta.respond(body(), deadline(), BUDGET.modelBy);
    expect(response.output_text).toBe(ANSWER);
    errors.push(await failure(meta.respond(body(), deadline(), BUDGET.modelBy)));
    await meta.respond(body(), deadline(), BUDGET.modelBy);
    errors.push(await failure(meta.respond(body(), deadline(), BUDGET.modelBy)));

    const lines = logged();
    expect(lines.some((line) => line.includes("meta_call_failed"))).toBe(true); // the capture works
    const kept = [...lines, JSON.stringify(meta.calls), ...errors.map((e) => `${String(e)} ${JSON.stringify(e)}`)];
    for (const text of kept) {
      for (const sentinel of [KEY, QUESTION, ANSWER, "Sentinel Street"]) expect(text).not.toContain(sentinel);
    }
    for (const err of errors) expect((err as Error).cause).toBeUndefined();
  });

  it("a fresh Meta starts with no calls, so each question's calls are its own", async () => {
    replies = [fail(429), ok("ask_call")];
    const first = createMeta(deps());
    await first.respond(body(), deadline(), BUDGET.modelBy);

    const second = createMeta(deps());

    expect(first.calls.map((c) => c.status)).toEqual([429, 200]);
    expect(second.calls).toEqual([]);
  });

  it("the SDK logs nothing of its own, even when OPENAI_LOG asks for debug", async () => {
    vi.stubEnv("OPENAI_LOG", "debug");
    replies = [ok("ask_answer"), fail(400)];
    const meta = createMeta(deps());

    await meta.respond(body(), deadline(), BUDGET.modelBy);
    await failure(meta.respond(body(), deadline(), BUDGET.modelBy));

    // Only the client's own line for the failed try.
    expect(logged()).toEqual([
      JSON.stringify({
        msg: "meta_call_failed",
        model: "muse-spark-1.3",
        status: 400,
        ms: 0,
        error_type: "error",
        error_code: "400",
        error_param: null,
      }),
    ]);
  });

  it("a failed try logs one line: its model, status and ms", async () => {
    replies = [fail(503)];

    await failure(createMeta(deps()).respond(body(), deadline(1000), BUDGET.modelBy));

    expect(logged().map((line) => JSON.parse(line))).toEqual([
      { msg: "meta_call_failed", model: "muse-spark-1.3", status: 503, ms: 0 },
    ]);
  });

  it("a 4xx's line adds Meta's error type, code and param, never its message", async () => {
    const message = `bad include for ${QUESTION} with ${KEY}`;
    replies = [{ status: 400, body: { error: { message, type: "invalid_request_error", code: "invalid_value", param: "include" } } }];

    await failure(createMeta(deps()).respond(body(), deadline(), BUDGET.modelBy));

    expect(logged().map((line) => JSON.parse(line))).toEqual([
      {
        msg: "meta_call_failed",
        model: "muse-spark-1.3",
        status: 400,
        ms: 0,
        error_type: "invalid_request_error",
        error_code: "invalid_value",
        error_param: "include",
      },
    ]);
    for (const line of logged()) for (const text of ["bad include", QUESTION, KEY]) expect(line).not.toContain(text);
  });

  it("a field that isn't a short identifier, or holds the key, is logged as null", async () => {
    replies = [{ status: 400, body: { error: { message: "m", type: "two words", code: "x".repeat(65), param: `p-${KEY}` } } }];

    await failure(createMeta(deps()).respond(body(), deadline(), BUDGET.modelBy));

    expect(JSON.parse(logged()[0])).toMatchObject({ error_type: null, error_code: null, error_param: null });
    expect(logged()[0]).not.toContain(KEY);
  });

  it("the fixtures carry a placeholder for every id, call_id and encrypted_content", () => {
    const found: string[] = [];
    const walk = (node: unknown): void => {
      if (Array.isArray(node)) node.forEach(walk);
      else if (typeof node === "object" && node !== null) {
        for (const [key, value] of Object.entries(node)) {
          if (["id", "call_id", "encrypted_content"].includes(key)) found.push(String(value));
          walk(value);
        }
      }
    };
    for (const name of ["ask_call", "ask_answer", "ask_offtopic", "ask_incomplete"]) walk(fixture(name));

    expect(found).toHaveLength(16);
    for (const value of found) expect(value).toMatch(/^[a-z]+_fixture_\d+$/);
  });
});

// --- transcription (spec §4.7, F5) -------------------------------------------------------------------------------

const WAV = Uint8Array.from([0x52, 0x49, 0x46, 0x46, 0x5e, 0x77, 0x11, 0x00, 0x57, 0x41, 0x56, 0x45]); // a sentinel run
const SPOKEN = "Sentinelspoken baha sa España?";
const OPTS = { keywords: ["España Blvd cor. Maceda St", "Taft Ave in front of PGH"], languageBias: ["Tagalog", "English"] };
// A Deadline whose transcription mark is `leftMs` away on the fake clock.
const voiceDeadline = (leftMs: number = BUDGET.transcribeBy) => new Deadline(clock - (BUDGET.transcribeBy - leftMs), () => clock);
const heard = (transcript: string): Reply => ({ status: 200, body: { ...fixture("transcribe"), transcript } });

describe("transcribe", () => {
  it("the transcription request's parts", async () => {
    replies = [ok("transcribe")];
    const meta = createMeta(deps());

    await meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy);

    expect(sent).toHaveLength(1);
    expect(sent[0].url).toBe("https://api.meta.ai/v1/asr/transcribe");
    expect(sent[0].method).toBe("POST");
    expect(sent[0].headers.get("authorization")).toBe(`Bearer ${KEY}`);
    expect(sent[0].headers.get("accept")).toBe("application/json");
    const form = sent[0].form as FormData;
    expect([...form.keys()]).toEqual(["request", "audio"]);
    const request = form.get("request") as Blob;
    expect(request.type).toBe("application/json");
    expect(JSON.parse(await request.text())).toEqual({
      model: "muse-voice-transcribe-1.0",
      audioEncoding: "WAV",
      mode: "PUSH_TO_TALK",
      keywords: OPTS.keywords,
      languageBias: ["Tagalog", "English"],
    });
    const audio = form.get("audio") as File;
    expect(audio.type).toBe("audio/wav");
    expect(new Uint8Array(await audio.arrayBuffer())).toEqual(WAV);
  });

  it("gives the transcript and its duration, and records the try under the transcription model", async () => {
    replies = [ok("transcribe")];
    const meta = createMeta(deps());

    const result = await meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy);

    expect(result).toEqual({ transcript: "Gaano kalalim ang baha sa España cor. Maceda?", audioDurationMs: 3700 });
    expect(meta.calls).toEqual([{ model: "muse-voice-transcribe-1.0", status: 200, ms: 0 }]);
  });

  it("only the two model ids are allowed, and muse-spark-1.3-contributor is refused", async () => {
    replies = [ok("transcribe"), ok("ask_call")];
    const meta = createMeta(deps());

    await meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy);
    await meta.respond(body(), deadline(), BUDGET.modelBy);
    await expect(meta.respond(body({ model: "muse-spark-1.3-contributor" }), deadline(), BUDGET.modelBy)).rejects.toThrow();

    expect(meta.calls.map((c) => c.model)).toEqual(["muse-voice-transcribe-1.0", "muse-spark-1.3"]);
    expect(sent).toHaveLength(2);
  });

  it("a 429 then a 200 makes two calls, inside the transcription mark", async () => {
    replies = [fail(429), ok("transcribe")];
    const meta = createMeta(deps());

    await meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy);

    expect(sent).toHaveLength(2);
    expect(sleeps).toEqual([1000]);
    expect(meta.calls.map((c) => c.status)).toEqual([429, 200]);
  });

  it("Retry-After past the transcription mark means no retry", async () => {
    replies = [fail(503, { "retry-after": "3" })];
    const meta = createMeta(deps());

    const err = await failure(meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy));

    expect(err.status).toBe(503);
    expect(sent).toHaveLength(1);
    expect(sleeps).toEqual([]);
  });

  it.each([400, 401, 402, 403, 504])("a %i throws with its status, once", async (status) => {
    replies = [fail(status)];
    const meta = createMeta(deps());

    const err = await failure(meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy));

    expect(err.status).toBe(status);
    expect(sent).toHaveLength(1);
    expect(meta.calls).toEqual([{ model: "muse-voice-transcribe-1.0", status, ms: 0 }]);
  });

  it("a 4xx's line adds the transcription's error type, code and param, never its message", async () => {
    // Meta's answer to the Oct 31 voice probe (C740), with its own message.
    const message = "ASR keyword 3 exceeds the maximum length of 30 characters";
    replies = [{ status: 400, body: { error: { message, type: "invalid_request_error", code: null, param: null } } }];

    await failure(createMeta(deps()).transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy));

    expect(logged().map((line) => JSON.parse(line))).toEqual([
      {
        msg: "meta_call_failed",
        model: "muse-voice-transcribe-1.0",
        status: 400,
        ms: 0,
        error_type: "invalid_request_error",
        error_code: null,
        error_param: null,
      },
    ]);
    expect(logged().join("\n")).not.toContain("ASR keyword");
  });

  it("a 5xx's body is never read, and its line has no error fields", async () => {
    let pulled = false;
    let cancelled = false;
    const errorBody = new ReadableStream(
      {
        pull: (controller) => {
          pulled = true;
          controller.enqueue(new TextEncoder().encode(JSON.stringify({ error: { type: "server_error" } })));
          controller.close();
        },
        cancel: () => {
          cancelled = true;
        },
      },
      { highWaterMark: 0 }, // pulled only when something reads it
    );
    replies = [() => Promise.resolve(new Response(errorBody, { status: 504, headers: { "content-type": "application/json" } }))];

    await failure(createMeta(deps()).transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy));

    expect({ pulled, cancelled }).toEqual({ pulled: false, cancelled: true });
    expect(logged().map((line) => JSON.parse(line))).toEqual([
      { msg: "meta_call_failed", model: "muse-voice-transcribe-1.0", status: 504, ms: 0 },
    ]);
  });

  it.each([
    ["no transcript", { audioDurationMs: 3700 }],
    ["a transcript that isn't text", { transcript: 7, audioDurationMs: 3700 }],
    ["a body that isn't JSON", "not json"],
  ])("a 200 with %s is MetaError(null), recorded as the 200 it was", async (_name, answer) => {
    replies = [
      typeof answer === "string"
        ? () => Promise.resolve(new Response(answer, { status: 200, headers: { "content-type": "application/json" } }))
        : { status: 200, body: answer },
    ];
    const meta = createMeta(deps());

    const err = await failure(meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy));

    expect(err.status).toBeNull();
    expect(meta.calls).toEqual([{ model: "muse-voice-transcribe-1.0", status: 200, ms: 0 }]);
    expect(logged().filter((line) => line.includes("meta_call_failed"))).toEqual([]);
  });

  it("a duration that is missing or not a number is null, since nothing reads it", async () => {
    replies = [
      { status: 200, body: { transcript: "baha" } },
      { status: 200, body: { transcript: "baha", audioDurationMs: "3700" } },
    ];
    const meta = createMeta(deps());

    expect(await meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy)).toEqual({ transcript: "baha", audioDurationMs: null });
    expect(await meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy)).toEqual({ transcript: "baha", audioDurationMs: null });
  });

  it("the transcription mark aborts a call in flight: MetaError(null)", async () => {
    const realStart = Date.now();
    replies = [
      (init) =>
        new Promise<Response>((_, reject) => {
          init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        }),
    ];
    const meta = createMeta(deps({ now: Date.now }));

    const err = await failure(meta.transcribe(WAV, OPTS, new Deadline(realStart - BUDGET.transcribeBy + 50, Date.now), BUDGET.transcribeBy));

    expect(err.status).toBeNull();
    expect(Date.now() - realStart).toBeGreaterThanOrEqual(45);
    expect(meta.calls.map((c) => c.status)).toEqual([null]);
  });

  it("a mark already past sends nothing", async () => {
    const meta = createMeta(deps());

    const err = await failure(meta.transcribe(WAV, OPTS, voiceDeadline(0), BUDGET.transcribeBy));

    expect(err.status).toBeNull();
    expect(sent).toHaveLength(0);
  });

  it("no log line, error or call record holds the key, the audio or the transcript", async () => {
    replies = [
      heard(SPOKEN),
      { status: 401, body: { error: { message: `bad key ${KEY} for ${SPOKEN}`, type: "auth" } } },
      () => Promise.reject(new TypeError(`fetch failed for ${KEY}`)),
    ];
    const meta = createMeta(deps());
    const errors: unknown[] = [];

    expect((await meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy)).transcript).toBe(SPOKEN);
    errors.push(await failure(meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy)));
    errors.push(await failure(meta.transcribe(WAV, OPTS, voiceDeadline(), BUDGET.transcribeBy)));

    const lines = logged();
    expect(lines.some((line) => line.includes("meta_call_failed"))).toBe(true);
    const audio = Buffer.from(WAV).toString("base64");
    const kept = [...lines, JSON.stringify(meta.calls), ...errors.map((e) => `${String(e)} ${JSON.stringify(e)}`)];
    for (const text of kept) {
      for (const sentinel of [KEY, SPOKEN, "Sentinelspoken", audio, "RIFF^w"]) expect(text).not.toContain(sentinel);
    }
  });
});
