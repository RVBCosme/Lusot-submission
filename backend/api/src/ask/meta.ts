import OpenAI, { APIError } from "openai";
import type { Response, ResponseCreateParamsNonStreaming } from "openai/resources/responses/responses";
import type { Deadline } from "./deadline";

const BASE_URL = "https://api.meta.ai/v1";
// Ask's two models (CLAUDE.md), never Muse Spark's contributor model. respond takes only Muse Spark, and transcribe
// names its own model.
export const MODEL = "muse-spark-1.3";
export const TRANSCRIBE_MODEL = "muse-voice-transcribe-1.0";
const RETRY_STATUSES = new Set([429, 500, 503]);
const MAX_TRIES = 3;
const BACKOFF_MS = 500; // before try n + 1: 500 ms × 2^(n − 1), plus jitter
const JITTER_MS = 1000;
// A retry is sent only if this much is left before the mark once its wait ends, so it can finish (spec §4.1).
// Task 2's probe timed a `low` turn at about 1.5 s at the median (turn 1 1.559 s, the final turn 1.147 s;
// docs/research/2026-10-30-ask-probe.md).
const MIN_TRY_MS = 1500;

export class MetaError extends Error {
  // The HTTP status; null for a timeout, an abort, a lost connection or an answer that couldn't be read.
  readonly status: number | null;

  constructor(status: number | null) {
    // A fixed message with no cause: Meta's own error text can echo part of the key, so none of it is kept.
    super(status === null ? "Meta gave no answer" : `Meta answered ${status}`);
    this.name = "MetaError";
    this.status = status;
  }
}

export type MetaCall = { model: string; status: number | null; ms: number };

export type MetaDeps = {
  key: string;
  fetchFn?: typeof fetch;
  sleep: (ms: number) => Promise<void>;
  random: () => number;
  now: () => number;
};

export type TranscribeOptions = { keywords: string[]; languageBias: string[] };

// A Meta belongs to one question: the handler (Task 12) creates one per question, so `calls` holds only that
// question's tries.
export type Meta = {
  respond(body: ResponseCreateParamsNonStreaming, deadline: Deadline, byMs: number): Promise<Response>;
  // One WAV clip, transcribed as one push-to-talk turn (spec §4.7, F5).
  transcribe(
    wav: Uint8Array,
    opts: TranscribeOptions,
    deadline: Deadline,
    byMs: number,
  ): Promise<{ transcript: string; audioDurationMs: number | null }>;
  // One entry per HTTP try, across every call on this instance, for the log line's meta_calls and meta_status.
  readonly calls: MetaCall[];
};

// The transcription's own non-2xx answer, read like the SDK's APIError: its status, its headers and, for a 4xx only,
// its body's `error` object, which only errorFields reads.
class HttpFailure extends Error {
  constructor(
    readonly status: number,
    readonly headers: Headers,
    readonly error: unknown,
  ) {
    super(`Meta answered ${status}`);
    this.name = "HttpFailure";
  }
}

// A 4xx's client-safe fields for its log line: Meta's error type, code and param, each only when it is a short
// identifier without the key in it, else null. The message is never read: it can echo the key or the question.
const SAFE_FIELD = /^[A-Za-z0-9_.:[\]-]{1,64}$/;

function errorFields(err: unknown, key: string): Record<string, string | null> {
  const status = statusOf(err);
  if (status === null || status < 400 || status > 499) return {};
  const error = (err instanceof APIError ? err : err instanceof HttpFailure ? err.error : undefined) as
    | { type?: unknown; code?: unknown; param?: unknown }
    | null
    | undefined;
  const safe = (value: unknown) => (typeof value === "string" && SAFE_FIELD.test(value) && !value.includes(key) ? value : null);
  return { error_type: safe(error?.type), error_code: safe(error?.code), error_param: safe(error?.param) };
}

// What one try gave: its HTTP status, and its answer, or undefined for a 2xx whose body wasn't the documented shape.
type Answered<T> = { status: number; value: T | undefined };

export function createMeta(deps: MetaDeps): Meta {
  const fetchFn = deps.fetchFn ?? globalThis.fetch;
  const client = new OpenAI({
    apiKey: deps.key,
    baseURL: BASE_URL,
    maxRetries: 0, // the loop below is the only retry
    logLevel: "off", // the SDK logs nothing of its own, so no request or answer text reaches a log
    fetch: deps.fetchFn,
  });
  const calls: MetaCall[] = [];

  // Tries `attempt` until it answers, a status that isn't 429, 500 or 503 ends it, 3 tries are made, or the next
  // try couldn't finish before the mark. Each try's signal aborts at the mark, and also stops reading the body.
  async function withRetries<T>(
    model: string,
    deadline: Deadline,
    byMs: number,
    attempt: (signal: AbortSignal) => Promise<Answered<T>>,
  ): Promise<T> {
    let last: MetaError | undefined;
    for (let tries = 1; ; tries++) {
      const signal = deadline.signal(byMs);
      if (signal.aborted) throw last ?? new MetaError(null); // nothing is sent once the mark has passed
      const started = deps.now();
      let answered: Answered<T>;
      try {
        answered = await attempt(signal);
      } catch (err) {
        const status = statusOf(err);
        const ms = deps.now() - started;
        calls.push({ model, status, ms });
        console.error(JSON.stringify({ msg: "meta_call_failed", model, status, ms, ...errorFields(err, deps.key) }));
        last = new MetaError(status);
        if (status === null || !RETRY_STATUSES.has(status) || tries >= MAX_TRIES) throw last;
        const backoffMs = BACKOFF_MS * 2 ** (tries - 1) + deps.random() * JITTER_MS;
        const waitMs = Math.max(backoffMs, retryAfterMs(headersOf(err), deps.now()));
        // A retry that couldn't finish before the mark isn't made: the status that called for it is thrown.
        if (deadline.remainingMs(byMs) - waitMs < MIN_TRY_MS) throw last;
        await deps.sleep(waitMs);
        continue;
      }
      const ms = deps.now() - started;
      calls.push({ model, status: answered.status, ms });
      if (answered.value !== undefined) return answered.value;
      // A 2xx it couldn't read: recorded as the answer it was, which may be billed, and never retried.
      console.error(JSON.stringify({ msg: "meta_answer_unreadable", model, status: answered.status, ms }));
      throw new MetaError(null);
    }
  }

  return {
    calls,
    async respond(body, deadline, byMs) {
      if (body.model !== MODEL) throw new Error(`Ask calls only ${MODEL}`);
      const sent = { ...body, store: false }; // never stored at Meta
      return withRetries(MODEL, deadline, byMs, async (signal) => {
        const { data, response } = await client.responses.create(sent, { signal }).withResponse();
        return { status: response.status, value: data };
      });
    },

    async transcribe(wav, opts, deadline, byMs) {
      // F5's request part. Meta keeps no `store` setting for audio (spec §4.9).
      const settings = JSON.stringify({
        model: TRANSCRIBE_MODEL,
        audioEncoding: "WAV",
        mode: "PUSH_TO_TALK",
        keywords: opts.keywords,
        languageBias: opts.languageBias,
      });
      return withRetries(TRANSCRIBE_MODEL, deadline, byMs, async (signal) => {
        const form = new FormData();
        form.append("request", new Blob([settings], { type: "application/json" }));
        form.append("audio", new Blob([new Uint8Array(wav)], { type: "audio/wav" }), "clip.wav");
        const res = await fetchFn(`${BASE_URL}/asr/transcribe`, {
          method: "POST",
          headers: { authorization: `Bearer ${deps.key}`, accept: "application/json" },
          body: form,
          signal,
        });
        if (!res.ok) {
          // A 4xx's body is read for errorFields alone; any other error's body is never read, so the connection is freed.
          let error: unknown;
          if (res.status >= 400 && res.status <= 499) {
            error = ((await res.json().catch(() => undefined)) as { error?: unknown } | undefined)?.error;
          } else {
            await res.body?.cancel().catch(() => {});
          }
          throw new HttpFailure(res.status, res.headers, error);
        }
        // A body that isn't JSON is a 2xx it can't read, as one without a transcript is.
        const body: unknown = await res.json().catch(() => undefined);
        return { status: res.status, value: readTranscript(body) };
      });
    },
  };
}

// The documented answer (F5): its transcript, or undefined without one. Its duration is kept when it is a number, and
// is null otherwise, since nothing bills or answers by it (the clip's own length is billed).
function readTranscript(body: unknown): { transcript: string; audioDurationMs: number | null } | undefined {
  const { transcript, audioDurationMs } = (body ?? {}) as Record<string, unknown>;
  if (typeof transcript !== "string") return undefined;
  const duration = typeof audioDurationMs === "number" && Number.isFinite(audioDurationMs) ? audioDurationMs : null;
  return { transcript, audioDurationMs: duration };
}

// A failed try's HTTP status: the SDK's APIError's or the transcription's own; null for anything else.
function statusOf(err: unknown): number | null {
  if (err instanceof APIError && typeof err.status === "number") return err.status;
  return err instanceof HttpFailure ? err.status : null;
}

function headersOf(err: unknown): Headers | undefined {
  if (err instanceof APIError || err instanceof HttpFailure) return err.headers;
  return undefined;
}

// The wait a Retry-After header asks for, given in seconds or as an HTTP date; 0 when there is none.
function retryAfterMs(headers: Headers | undefined, nowMs: number): number {
  const value = headers?.get("retry-after")?.trim();
  if (!value) return 0;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
  const at = Date.parse(value);
  return Number.isNaN(at) ? 0 : Math.max(0, at - nowMs);
}
