// The wait for a report's result (spec C601): every 2 s for the first minute, every 5 s until 4 minutes,
// then every 15 s, up to 10 minutes after the upload. Past that the screen says "No result yet", never a
// failure the server hasn't reported, and "Check again" polls the same report; nothing here uploads.
import { getReport, HttpError, RequestTimeoutError, type ReportResult } from './api'

export const POLL = {
  fastMs: 2000,
  fastForMs: 60_000,
  midMs: 5000,
  midForMs: 240_000,
  slowMs: 15_000,
  windowMs: 600_000,
} as const

const FINAL_STATUSES = new Set(['done', 'refused', 'failed'])
const JITTER_MS = 1000 // a 429 without a readable Retry-After waits the interval plus up to this

// The wait before the next poll, by the time since the upload finished.
export function intervalAt(elapsedMs: number): number {
  if (elapsedMs < POLL.fastForMs) return POLL.fastMs
  if (elapsedMs < POLL.midForMs) return POLL.midMs
  return POLL.slowMs
}

// No final status by the deadline: read as "no result yet" (C601), never as processing failed. Its message
// names no report id.
export class PollTimeoutError extends Error {
  constructor(windowMs: number) {
    super(`No result yet after ${windowMs / 1000} s`)
    this.name = 'PollTimeoutError'
  }
}

export interface PollOptions {
  fetchFn?: typeof fetch
  // Wakes early when the signal aborts, if it can; the loop checks the signal after it either way.
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>
  now?: () => number
  random?: () => number
  signal?: AbortSignal
  // Where the schedule starts: 0 right after the upload, 240_000 for "Check again" (every 15 s).
  startElapsedMs?: number
  // The deadline as a time on the `now` clock. Left out, it is 600 s after this call. A poll restarted mid-wait
  // (after the app comes back to the front) passes the upload's time plus POLL.windowMs, so the total stays
  // 600 s. "Check again" leaves it out, for a new 600 s window. One that isn't a finite number counts as left out,
  // so a NaN can never make the poll run forever.
  deadlineAt?: number
}

// Polls GET /reports/{id} until the report has a final status (R32). The deadline is on the clock, so the time
// requests take counts too; the last poll comes at the deadline. A poll started past it makes one last check.
// - A 404, a 5xx, a network error, a request timeout or an answer that isn't JSON keeps polling.
// - A 429 waits for its Retry-After when the browser can read it (N15), never less than the interval and
//   never past the deadline, or else for the interval plus up to 1 s of jitter.
// - Any other 4xx throws its HttpError. An aborted signal cancels the request in flight and throws an
//   AbortError before the next fetch.
export async function pollReport(
  apiUrl: string,
  reportId: string,
  {
    // Left out, getReport applies its own default: apiFetch.
    fetchFn,
    sleep = abortableSleep,
    now = Date.now,
    random = Math.random,
    signal,
    startElapsedMs = 0,
    deadlineAt,
  }: PollOptions = {},
): Promise<ReportResult> {
  const startedAt = now()
  const endAt = deadlineAt !== undefined && Number.isFinite(deadlineAt) ? deadlineAt : startedAt + POLL.windowMs
  for (;;) {
    stopIfAborted(signal)
    let report: ReportResult | undefined
    let failure: unknown
    try {
      report = await getReport(apiUrl, reportId, fetchFn, signal)
    } catch (err) {
      failure = err
    }
    stopIfAborted(signal)
    if (failure !== undefined && !keepsPolling(failure)) throw failure
    if (report !== undefined && FINAL_STATUSES.has(report.status)) return report

    const at = now()
    if (at >= endAt) throw new PollTimeoutError(POLL.windowMs)
    const interval = intervalAt(startElapsedMs + (at - startedAt))
    let wait = interval
    if (failure instanceof HttpError && failure.status === 429) {
      wait = failure.retryAfterMs === undefined ? interval + random() * JITTER_MS : Math.max(failure.retryAfterMs, interval)
    }
    await sleep(Math.min(wait, endAt - at), signal)
  }
}

// Failures that aren't the server's word on the report: the next poll may get through.
function keepsPolling(err: unknown): boolean {
  if (err instanceof HttpError) return err.status >= 500 || err.status === 429
  return err instanceof TypeError || err instanceof SyntaxError || err instanceof RequestTimeoutError
}

function stopIfAborted(signal: AbortSignal | undefined): void {
  if (signal?.aborted) throw new DOMException('The poll was stopped', 'AbortError')
}

function abortableSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const wake = () => {
      clearTimeout(timer)
      signal?.removeEventListener('abort', wake)
      resolve()
    }
    const timer = setTimeout(wake, ms)
    signal?.addEventListener('abort', wake, { once: true })
  })
}
