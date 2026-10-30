// The fixtures in test/fixtures/meta/ take their shapes and numbers from Task 2's probe (Oct 30; its saved calls
// in the private data folder): ask_call.json from a `low` turn 1 that called get_reports, ask_answer.json from
// the turn that answered it, and ask_offtopic.json from the off-topic question. The probe saved each call's
// status, token counts, tool arguments and answer, not the raw body, so the envelope follows Meta's Responses
// schema (dev.meta.ai/docs/api-reference/responses/schemas), and every id, call_id and encrypted_content is a
// placeholder. The probe had no incomplete response, so ask_incomplete.json is written by hand.
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
type Sent = { url: string; method: string | undefined; headers: Headers; body: Record<string, unknown> };

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
  sent.push({
    url: String(input),
    method: init?.method,
    headers: new Headers(init?.headers),
    body: JSON.parse(String(init?.body)),
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

  it("the SDK logs nothing of its own, even when OPENAI_LOG asks for debug", async () => {
    vi.stubEnv("OPENAI_LOG", "debug");
    replies = [ok("ask_answer"), fail(400)];
    const meta = createMeta(deps());

    await meta.respond(body(), deadline(), BUDGET.modelBy);
    await failure(meta.respond(body(), deadline(), BUDGET.modelBy));

    // Only the client's own line for the failed try.
    expect(logged()).toEqual([JSON.stringify({ msg: "meta_call_failed", model: "muse-spark-1.3", status: 400, ms: 0 })]);
  });

  it("a failed try logs one line: its model, status and ms", async () => {
    replies = [fail(400)];

    await failure(createMeta(deps()).respond(body(), deadline(), BUDGET.modelBy));

    expect(logged().map((line) => JSON.parse(line))).toEqual([
      { msg: "meta_call_failed", model: "muse-spark-1.3", status: 400, ms: 0 },
    ]);
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
