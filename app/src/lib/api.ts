// The HTTP API (POST /uploads, GET /reports/{id}) and the presigned S3 upload.

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

// A non-2xx response. `code` is the API's `error` value, such as "capture_too_old", when the body has one.
export class HttpError extends Error {
  readonly status: number
  readonly code: string | undefined

  constructor(status: number, code?: string) {
    super(code === undefined ? `HTTP ${status}` : `HTTP ${status} ${code}`)
    this.name = 'HttpError'
    this.status = status
    this.code = code
  }
}

export async function requestUpload(
  apiUrl: string,
  req: UploadRequest,
  fetchFn: typeof fetch = fetch,
): Promise<{ reportId: string; upload: PresignedPost }> {
  const res = await fetchFn(`${apiUrl}/uploads`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw await httpError(res)
  const { reportId, upload } = await res.json()
  return { reportId, upload }
}

export async function postToS3(upload: PresignedPost, jpeg: Blob, fetchFn: typeof fetch = fetch): Promise<void> {
  // The policy's fields (Content-Type: image/jpeg among them) go first: S3 ignores fields after the file.
  const form = new FormData()
  for (const [name, value] of Object.entries(upload.fields)) form.append(name, value)
  form.append('file', jpeg)
  const res = await fetchFn(upload.url, { method: 'POST', body: form })
  if (!res.ok) throw await httpError(res)
}

const FINAL_STATUSES = new Set(['done', 'refused', 'failed'])

// Polls until the report has a final status (R32): pending and processing are still in progress.
// A 404 means the reports index hasn't caught up with a fresh report yet, so it keeps polling (R30).
export async function pollReport(
  apiUrl: string,
  reportId: string,
  { intervalMs = 2000, timeoutMs = 120_000 }: { intervalMs?: number; timeoutMs?: number } = {},
  fetchFn: typeof fetch = fetch,
  sleep: (ms: number) => Promise<void> = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
): Promise<ReportResult> {
  for (let waitedMs = 0; ; waitedMs += intervalMs) {
    const res = await fetchFn(`${apiUrl}/reports/${reportId}`)
    if (res.ok) {
      const { status, refusalReason } = await res.json()
      if (FINAL_STATUSES.has(status)) return { status, refusalReason }
    } else if (res.status !== 404) {
      throw await httpError(res)
    }
    if (waitedMs + intervalMs > timeoutMs) throw new Error(`No result for report ${reportId} after ${timeoutMs / 1000} s`)
    await sleep(intervalMs)
  }
}

async function httpError(res: Response): Promise<HttpError> {
  // S3 answers in XML, so a body that isn't JSON leaves only the status.
  const body: unknown = await res.json().catch(() => undefined)
  const code = (body as { error?: unknown } | null | undefined)?.error
  return new HttpError(res.status, typeof code === 'string' ? code : undefined)
}
