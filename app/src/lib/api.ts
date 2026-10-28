// The HTTP API (POST /uploads, GET /reports/{id}) and the presigned S3 upload.

const REQUEST_TIMEOUT_MS = 15_000 // one API call
const UPLOAD_TIMEOUT_MS = 60_000 // the photo: a few hundred KB, maybe over a slow mobile connection
const FINAL_STATUSES = new Set(['done', 'refused', 'failed'])

export interface UploadRequest {
  lat: number
  lng: number
  gpsAccuracyM: number
  capturedAt: string // ISO 8601 with a time zone
}

export interface PresignedPost {
  url: string
  fields: Record<string, string>
}

export interface ReportResult {
  status: string
  refusalReason?: string
}

// A non-2xx response. `code` and `detail` are the API's `error` and `detail` values, when the body has them.
export class HttpError extends Error {
  readonly status: number
  readonly code: string | undefined
  readonly detail: string | undefined

  constructor(status: number, code?: string, detail?: string) {
    super(`HTTP ${status}${code === undefined ? '' : ` ${code}`}${detail === undefined ? '' : `: ${detail}`}`)
    this.name = 'HttpError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

// The API's base URL from VITE_API_URL without trailing slashes, or '' when it isn't set.
export function apiBaseUrl(raw: string | undefined): string {
  return (raw ?? '').replace(/\/+$/, '')
}

export async function requestUpload(
  apiUrl: string,
  req: UploadRequest,
  fetchFn: typeof fetch = fetch,
): Promise<{ reportId: string; upload: PresignedPost }> {
  return withTimeout(REQUEST_TIMEOUT_MS, async (signal) => {
    const res = await fetchFn(`${apiUrl}/uploads`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(req),
      signal,
    })
    if (!res.ok) throw await httpError(res)
    const { reportId, upload } = await res.json()
    return { reportId, upload }
  })
}

export async function postToS3(upload: PresignedPost, jpeg: Blob, fetchFn: typeof fetch = fetch): Promise<void> {
  // The policy's fields (Content-Type: image/jpeg among them) go first: S3 ignores fields after the file.
  const form = new FormData()
  for (const [name, value] of Object.entries(upload.fields)) form.append(name, value)
  form.append('file', jpeg)
  await withTimeout(UPLOAD_TIMEOUT_MS, async (signal) => {
    const res = await fetchFn(upload.url, { method: 'POST', body: form, signal })
    if (!res.ok) throw await httpError(res)
  })
}

// Polls until the report has a final status (R32): pending and processing are still in progress.
// A 404 means the reports index hasn't caught up with a fresh report yet, so it keeps polling (R30).
// The deadline is on the clock, so the time requests take counts too.
export async function pollReport(
  apiUrl: string,
  reportId: string,
  { intervalMs = 2000, timeoutMs = 120_000 }: { intervalMs?: number; timeoutMs?: number } = {},
  fetchFn: typeof fetch = fetch,
  sleep: (ms: number) => Promise<void> = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
): Promise<ReportResult> {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const report = await withTimeout(REQUEST_TIMEOUT_MS, async (signal): Promise<ReportResult | undefined> => {
      const res = await fetchFn(`${apiUrl}/reports/${reportId}`, { signal })
      if (res.status === 404) return undefined
      if (!res.ok) throw await httpError(res)
      const { status, refusalReason } = await res.json()
      return { status, refusalReason }
    })
    if (report !== undefined && FINAL_STATUSES.has(report.status)) return report
    if (Date.now() + intervalMs > deadline) throw new Error(`No result for report ${reportId} after ${timeoutMs / 1000} s`)
    await sleep(intervalMs)
  }
}

// Runs one request, body included, with a time limit, so a stalled connection fails instead of
// leaving the screen waiting. The race settles on time even if a fetch ignores the abort.
async function withTimeout<T>(timeoutMs: number, request: (signal: AbortSignal) => Promise<T>): Promise<T> {
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  const timedOut = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort()
      reject(new Error(`No answer after ${timeoutMs / 1000} s`))
    }, timeoutMs)
  })
  try {
    return await Promise.race([request(controller.signal), timedOut])
  } finally {
    clearTimeout(timer)
  }
}

async function httpError(res: Response): Promise<HttpError> {
  // S3 answers in XML, so a body that isn't JSON leaves only the status.
  const body: unknown = await res.json().catch(() => undefined)
  const { error, detail } = (body ?? {}) as { error?: unknown; detail?: unknown }
  return new HttpError(
    res.status,
    typeof error === 'string' ? error : undefined,
    typeof detail === 'string' ? detail : undefined,
  )
}
