// One retry for a call that failed on the way, not by the server's decision (spec C635): about 2 s later, on a
// network error, a request timeout, a 503 other than MS1's uploads_paused, or API Gateway's throttling 429,
// which alone carries no error code (MS4's C522). A 429 with any code (device_limit, global_cap, question_limit,
// question_cap, or one this app doesn't know) is a limit, and never retried. For POST /uploads
// and the S3 upload only: a retried upload request makes a report that never gets a photo, and a retried S3
// upload reuses the same link, so the photo is analysed and paid for once.
import { HttpError, RequestTimeoutError } from './api'

const RETRY_DELAY_MS = 2000

export async function retryOnce<T>(
  call: () => Promise<T>,
  { delayMs = RETRY_DELAY_MS, sleep = wait }: { delayMs?: number; sleep?: (ms: number) => Promise<void> } = {},
): Promise<T> {
  try {
    return await call()
  } catch (err) {
    if (!worthRetrying(err)) throw err
    await sleep(delayMs)
    return call()
  }
}

function worthRetrying(err: unknown): boolean {
  if (err instanceof TypeError || err instanceof RequestTimeoutError) return true
  if (!(err instanceof HttpError)) return false
  if (err.status === 503) return err.code !== 'uploads_paused'
  return err.status === 429 && err.code === undefined
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
