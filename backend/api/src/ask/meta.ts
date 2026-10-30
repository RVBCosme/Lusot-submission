import OpenAI, { APIError } from "openai";
import type { Response, ResponseCreateParamsNonStreaming } from "openai/resources/responses/responses";
import type { Deadline } from "./deadline";

const BASE_URL = "https://api.meta.ai/v1";
// Ask is typed only, so Muse Spark is the one model it calls, and never its contributor model.
const MODEL = "muse-spark-1.3";
const RETRY_STATUSES = new Set([429, 500, 503]);
const MAX_TRIES = 3;
const BACKOFF_MS = 500; // before try n + 1: 500 ms × 2^(n − 1), plus jitter
const JITTER_MS = 1000;

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

export type Meta = {
  respond(body: ResponseCreateParamsNonStreaming, deadline: Deadline, byMs: number): Promise<Response>;
  // One entry per HTTP try, for the log line's meta_calls and meta_status.
  readonly calls: MetaCall[];
};

export function createMeta(deps: MetaDeps): Meta {
  const client = new OpenAI({
    apiKey: deps.key,
    baseURL: BASE_URL,
    maxRetries: 0, // the loop below is the only retry
    logLevel: "off", // the SDK logs nothing of its own, so no request or answer text reaches a log
    fetch: deps.fetchFn,
  });
  const calls: MetaCall[] = [];

  return {
    calls,
    async respond(body, deadline, byMs) {
      if (body.model !== MODEL) throw new Error(`Ask calls only ${MODEL}`);
      const sent = { ...body, store: false }; // never stored at Meta
      let last: MetaError | undefined;
      for (let tries = 1; ; tries++) {
        // Each try's signal aborts at the mark, and also stops reading the body.
        const signal = deadline.signal(byMs);
        if (signal.aborted) throw last ?? new MetaError(null); // nothing is sent once the mark has passed
        const started = deps.now();
        try {
          const { data, response } = await client.responses.create(sent, { signal }).withResponse();
          calls.push({ model: MODEL, status: response.status, ms: deps.now() - started });
          return data;
        } catch (err) {
          const status = err instanceof APIError && typeof err.status === "number" ? err.status : null;
          const ms = deps.now() - started;
          calls.push({ model: MODEL, status, ms });
          console.error(JSON.stringify({ msg: "meta_call_failed", model: MODEL, status, ms }));
          last = new MetaError(status);
          if (status === null || !RETRY_STATUSES.has(status) || tries >= MAX_TRIES) throw last;
          const backoffMs = BACKOFF_MS * 2 ** (tries - 1) + deps.random() * JITTER_MS;
          const waitMs = Math.max(backoffMs, retryAfterMs((err as APIError).headers, deps.now()));
          // A wait that would end at or past the mark isn't taken.
          if (waitMs >= deadline.remainingMs(byMs)) throw last;
          await deps.sleep(waitMs);
        }
      }
    },
  };
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
