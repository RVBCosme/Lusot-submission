// The app's only route to the backend: MS4's HTTP API, the presigned S3 upload, and the layers file a
// report links to. Field names and error codes are MS4's committed ones (plan "Notes").
import { type Level, LEVELS, PASSABILITY, type Passability } from '../copy/levels'
import { apiFetch } from './apiFetch'

const REQUEST_TIMEOUT_MS = 15_000 // one API call
// Ask Lusot's two calls wait as long as API Gateway's own 30 s limit: the Lambda answers by 15 s at the latest, and a
// spoken question's upload comes first (Ask's spec §4.1). A question given up on may still be counted and paid.
const ASK_TIMEOUT_MS = 30_000
// API Gateway's throttling 429 refuses a question before the Lambda runs, so it is retried once, this much later.
const ASK_THROTTLE_RETRY_MS = 2000
const UPLOAD_TIMEOUT_MS = 60_000 // the photo: a few hundred KB, maybe over a slow mobile connection
// MS4's C508: the random device id, sent with uploads, samples and flags only (C606).
const DEVICE_HEADER = 'X-Lusot-Device'
// A limit's 429 codes (MS4's C522; Ask Lusot's, amendment 4; the day's cap, C534): shown, never retried.
const LIMIT_CODES = new Set(['device_limit', 'global_cap', 'daily_cap', 'question_limit', 'question_cap'])
// A sample's licence (C617, MS4's C512): CC0 or CC BY of any version, or MS4's exact value for a consented photo.
const SAMPLE_LICENCE = /^(CC0( 1\.0)?|CC BY \d(\.\d)?)$/
const CONSENTED_LICENCE = 'used with permission'
// Task 4's 9 levels and 3 classes. A pin outside them would break the wording of every viewer's map list.
const KNOWN_LEVELS: ReadonlySet<unknown> = new Set(LEVELS)
const KNOWN_CLASSES: ReadonlySet<unknown> = new Set(Object.values(PASSABILITY))

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

// MS4's layers file (its C524). Coordinates are the stored photo's pixels.
export type Point = [number, number]
export type Polygon = Point[]

// One numbered reference. A dropped one has a null level, level_from and level_is_floor, and `dropped` holds its cause.
// `level_is_floor` (MS4's C54) is true for a floor reading ("this level or deeper"), false for an exact one, and null
// where there is no level. A file from before MS4 added it has no such key, which the app reads as "not a floor".
export type OverlayRef = {
  id: number
  kind: 'wheel' | 'body' | 'person'
  box: [number, number, number, number]
  outline: Polygon[]
  landmark: string | null
  level: Level | null
  level_from: 'landmark' | 'geometry' | null
  level_is_floor: boolean | null
  used: boolean
  dropped: string | null
  rechecked: boolean
  rim_outline: Polygon[] | null
  rim: { center: Point; axes: Point; angle: number } | null
  waterline: [Point, Point] | null
}

export type OverlayData = { version: 1; width: number; height: number; water: Polygon[]; refs: OverlayRef[] }

// MS4's C507: `level` and `inches` are null on a dropped reference; `inches` comes only past the release gate.
// `levelIsFloor` is the reading's own C54 floor: true, false, or null where it has no level; an answer from before MS4
// added it has no such key.
export type Reading = {
  id: number
  kind: 'wheel' | 'body' | 'person'
  landmark: string | null
  level: Level | null
  levelIsFloor?: boolean | null
  inches?: [number, number] | null
  used: boolean
  dropped: string | null
}

// GET /reports/{id} (MS4's §4.3): MS3a's C67 fields, the mode and publish state, and for a level result its
// readings and short-lived links (C503). A demo pin adds its credit, place and event (C523).
export interface ReportResult {
  reportId: string
  status: string
  mode: 'live' | 'private' | 'sample' | 'eval' | 'demo' | 'try'
  published: boolean
  capturedAt?: string
  refusalReason?: string
  // A done report always has noFloodSeen. Only a level brings the rest (C67).
  noFloodSeen?: boolean
  level?: Level
  landmark?: string
  passability?: Passability
  basis?: { vehicles: number; people: number }
  levelIsFloor?: boolean
  levelFrom?: 'landmark' | 'geometry'
  depthInMin?: number
  depthInMax?: number
  gpsAccuracyM?: number
  readings?: Reading[]
  photoUrl?: string
  overlayUrl?: string
  layersUrl?: string
  credit?: string
  place?: string
  event?: string
}

// A public pin (MS4's §4.4). Every published pin is a level result (C506); only a demo pin has credit, place and event.
export type Pin = {
  id: string
  lat: number
  lng: number
  capturedAt: string
  mode: 'live' | 'demo'
  flags: number
  gpsAccuracyM: number | null
  level: Level
  landmark: string
  passability: Passability
  levelIsFloor: boolean
  basis: { vehicles: number; people: number }
  credit?: string
  place?: string
  event?: string
  depthInMin?: number
  depthInMax?: number
}

// Ask Lusot's answer (its spec §5.3): data only, which ask/render.ts words. Each report is a public pin with its
// distance from the place asked about, in whole metres.
export type AskReport = Pin & { distanceM: number }
export type AskKind =
  | 'reports'
  | 'no_reports'
  | 'place_too_broad'
  | 'no_place'
  | 'lookup_unavailable'
  | 'outside_metro_manila'
  | 'no_location'
  | 'off_topic'
  | 'no_speech'
export type AskAnswer = {
  source: 'model' | 'plain_list'
  fallback: 'model_calls_paused' | 'deadline' | 'model_error' | 'key_rejected' | 'invalid_answer' | 'no_tool_call' | null
  kind: AskKind
  crossing: boolean
  vehicle: 'light' | 'heavy' | 'on_foot' | null
  place: { name: string; source: 'spots' | 'nominatim' | 'here' } | null
  windowMin: number
  radiusM: number
  count: number
  reports: AskReport[]
  demo: AskReport[]
  deepestId: string | null
  cited: string[]
  suggestions: string[]
}
// "Use my location": a fix of 100 m or better (Ask's spec §5.1).
export type Here = { lat: number; lng: number; accuracyM: number }

// One entry of GET /samples (MS4's C512). photoUrl lasts 5 minutes.
export type Sample = {
  sampleId: string
  credit: string
  license: string
  place?: string
  date?: string
  event?: string
  photoUrl?: string
}

// A sample run while model calls are paused (MS4's C527, amendment 10): the seeding run's result, saved and dated.
// noFloodSeen only on done, the level fields only with a level, refusalReason only when refused; no basis,
// overlay or inches.
export type SavedSample = {
  saved: true
  savedAt: string
  result: {
    status: 'done' | 'refused'
    refusalReason?: string
    noFloodSeen?: boolean
    level?: Level
    landmark?: string
    passability?: Passability
    levelIsFloor?: boolean
  }
}

// The fields each answer is read for, so nothing else the API sends reaches the app's state.
const REPORT_FIELDS = [
  'reportId',
  'status',
  'mode',
  'capturedAt',
  'refusalReason',
  'noFloodSeen',
  'level',
  'landmark',
  'passability',
  'basis',
  'levelIsFloor',
  'levelFrom',
  'depthInMin',
  'depthInMax',
  'gpsAccuracyM',
  'readings',
  'photoUrl',
  'overlayUrl',
  'layersUrl',
  'credit',
  'place',
  'event',
] as const
const PIN_FIELDS = [
  'id',
  'lat',
  'lng',
  'capturedAt',
  'mode',
  'flags',
  'gpsAccuracyM',
  'level',
  'landmark',
  'passability',
  'levelIsFloor',
  'basis',
  'credit',
  'place',
  'event',
  'depthInMin',
  'depthInMax',
] as const
const SAMPLE_FIELDS = ['sampleId', 'credit', 'license', 'place', 'date', 'event', 'photoUrl'] as const
const SAVED_RESULT_FIELDS = [
  'status',
  'refusalReason',
  'noFloodSeen',
  'level',
  'landmark',
  'passability',
  'levelIsFloor',
] as const

// A non-2xx response. `code` and `detail` are the API's `error` and `detail` values, when the body has them.
// `retryAfterMs` comes from a Retry-After in whole seconds, readable once MS4's CORS exposes it (N15).
export class HttpError extends Error {
  readonly status: number
  readonly code: string | undefined
  readonly detail: string | undefined
  readonly retryAfterMs: number | undefined
  // A limit's 429, which is shown and never retried, unlike API Gateway's own throttle (MS4's C522).
  readonly isDeviceLimit: boolean

  constructor(status: number, code?: string, detail?: string, retryAfterMs?: number) {
    super(`HTTP ${status}${code === undefined ? '' : ` ${code}`}${detail === undefined ? '' : `: ${detail}`}`)
    this.name = 'HttpError'
    this.status = status
    this.code = code
    this.detail = detail
    this.retryAfterMs = retryAfterMs
    this.isDeviceLimit = status === 429 && code !== undefined && LIMIT_CODES.has(code)
  }
}

// A request that got no answer in its time limit. Its message names no URL, so no report id.
export class RequestTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`No answer after ${timeoutMs / 1000} s`)
    this.name = 'RequestTimeoutError'
  }
}

// An answer that isn't in the shape the API promises. A named error, so retryOnce never takes it for a network
// error: the server has already acted on the request. Its message names the route, never the body or an id.
export class MalformedAnswerError extends Error {
  constructor(route: string) {
    super(`${route} gave an answer in an unexpected shape`)
    this.name = 'MalformedAnswerError'
  }
}

// The API's base URL from VITE_API_URL without trailing slashes, or '' when it isn't set.
export function apiBaseUrl(raw: string | undefined): string {
  return (raw ?? '').replace(/\/+$/, '')
}

// POST /uploads. Only the request's own fields are sent.
export async function requestUpload(
  apiUrl: string,
  req: UploadRequest & { nudgeM: number; consentVersion: string },
  deviceId: string,
  fetchFn: typeof fetch = apiFetch,
): Promise<{ reportId: string; upload: PresignedPost }> {
  const { lat, lng, gpsAccuracyM, capturedAt, nudgeM, consentVersion } = req
  return withTimeout(REQUEST_TIMEOUT_MS, async (signal) => {
    const res = await fetchFn(`${apiUrl}/uploads`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', [DEVICE_HEADER]: deviceId },
      body: JSON.stringify({ lat, lng, gpsAccuracyM, capturedAt, nudgeM, consentVersion }),
      signal,
    })
    if (!res.ok) throw await httpError(res)
    const { reportId, upload } = ((await res.json()) ?? {}) as { reportId?: unknown; upload?: unknown }
    if (typeof reportId !== 'string' || !isPresignedPost(upload)) throw new MalformedAnswerError('POST /uploads')
    return { reportId, upload }
  })
}

// POST /try (MS4's C534): a photo the person chose, for a result only they see. Only the consent version is sent,
// with no place or time. Never retried: a link whose answer was lost may already be counted against the day's cap.
export async function requestTry(
  apiUrl: string,
  consentVersion: string,
  deviceId: string,
  fetchFn: typeof fetch = apiFetch,
): Promise<{ reportId: string; upload: PresignedPost }> {
  return withTimeout(REQUEST_TIMEOUT_MS, async (signal) => {
    const res = await fetchFn(`${apiUrl}/try`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', [DEVICE_HEADER]: deviceId },
      body: JSON.stringify({ consentVersion }),
      signal,
    })
    if (!res.ok) throw await httpError(res)
    const { reportId, upload } = ((await res.json()) ?? {}) as { reportId?: unknown; upload?: unknown }
    if (typeof reportId !== 'string' || !isPresignedPost(upload)) throw new MalformedAnswerError('POST /try')
    return { reportId, upload }
  })
}

export async function postToS3(upload: PresignedPost, jpeg: Blob, fetchFn: typeof fetch = apiFetch): Promise<void> {
  // The policy's fields (Content-Type: image/jpeg among them) go first: S3 ignores fields after the file.
  const form = new FormData()
  for (const [name, value] of Object.entries(upload.fields)) form.append(name, value)
  form.append('file', jpeg)
  await withTimeout(UPLOAD_TIMEOUT_MS, async (signal) => {
    const res = await fetchFn(upload.url, { method: 'POST', body: form, signal })
    if (!res.ok) throw await httpError(res)
  })
}

// GET /reports/{id}, or undefined on a 404: a fresh report the index hasn't caught up with (R30), or one past
// expiresAt (MS4's C526). For a published pin it carries the photo links while the pin is visible (C503).
// `stop` (the poll's signal) cancels the request in flight.
export async function getReport(
  apiUrl: string,
  id: string,
  fetchFn: typeof fetch = apiFetch,
  stop?: AbortSignal,
): Promise<ReportResult | undefined> {
  return withTimeout(
    REQUEST_TIMEOUT_MS,
    async (signal) => {
      const res = await fetchFn(`${apiUrl}/reports/${encodeURIComponent(id)}`, { signal })
      if (res.status === 404) return undefined
      if (!res.ok) throw await httpError(res)
      const body = await res.json()
      return { ...pick(body, REPORT_FIELDS), published: body.published === true } as unknown as ReportResult
    },
    stop,
  )
}

// The layers file a level result links to (layersUrl), or undefined on any failure: an expired link, a bucket
// without GET in its CORS rule (N14), a timeout, or a file that doesn't parse as C524's shape. The overlay
// JPEG stands in for it.
export async function getLayers(layersUrl: string, fetchFn: typeof fetch = apiFetch): Promise<OverlayData | undefined> {
  try {
    return await withTimeout(REQUEST_TIMEOUT_MS, async (signal) => {
      const res = await fetchFn(layersUrl, { signal })
      if (!res.ok) return undefined
      const data: unknown = await res.json()
      return isOverlayData(data) ? data : undefined
    })
  } catch {
    return undefined
  }
}

// GET /map/pins (MS4's C519): every visible published pin, live and demo. A pin without an id or a position
// can't be placed, one outside the 9 levels or 3 classes can't be worded, and a demo pin without its credit is
// never shown (N2).
export async function getPins(apiUrl: string, fetchFn: typeof fetch = apiFetch): Promise<Pin[]> {
  const { pins } = await getJson(`${apiUrl}/map/pins`, fetchFn)
  if (!Array.isArray(pins)) throw new MalformedAnswerError('GET /map/pins')
  return pins.filter(isUsablePin).map((pin) => pick(pin, PIN_FIELDS) as unknown as Pin)
}

// GET /samples (MS4's C512). A sample is kept only with a credit and a licence on the allow-list (C617).
export async function getSamples(apiUrl: string, fetchFn: typeof fetch = apiFetch): Promise<Sample[]> {
  const { samples } = await getJson(`${apiUrl}/samples`, fetchFn)
  if (!Array.isArray(samples)) throw new MalformedAnswerError('GET /samples')
  return samples.filter(isUsableSample).map((sample) => pick(sample, SAMPLE_FIELDS) as unknown as Sample)
}

// POST /samples/{sampleId}: a 201 starts a paid run and gives its report id; while model calls are paused, a 200
// gives the saved answer (MS4's C527). A 503 uploads_paused or a 404 not_found throws HttpError. Never retried:
// a run whose answer was lost may already be paid for.
export async function runSample(
  apiUrl: string,
  sampleId: string,
  deviceId: string,
  fetchFn: typeof fetch = apiFetch,
): Promise<{ reportId: string } | SavedSample> {
  return withTimeout(REQUEST_TIMEOUT_MS, async (signal) => {
    const res = await fetchFn(`${apiUrl}/samples/${encodeURIComponent(sampleId)}`, {
      method: 'POST',
      headers: { [DEVICE_HEADER]: deviceId },
      signal,
    })
    if (!res.ok) throw await httpError(res)
    const body = await res.json()
    if (body?.saved === true) {
      return { saved: true, savedAt: body.savedAt, result: pick(body.result, SAVED_RESULT_FIELDS) } as SavedSample
    }
    if (typeof body?.reportId !== 'string') throw new MalformedAnswerError('POST /samples/{sampleId}')
    return { reportId: body.reportId }
  })
}

// POST /reports/{id}/flag (MS4's §4.3). A repeat from the same phone answers 200 with the count unchanged
// (C522), and the count can lag by one (amendment 9). A 404 (a demo pin, or one off the map) throws HttpError.
export async function flagPin(
  apiUrl: string,
  id: string,
  deviceId: string,
  fetchFn: typeof fetch = apiFetch,
): Promise<{ flags: number }> {
  return withTimeout(REQUEST_TIMEOUT_MS, async (signal) => {
    const res = await fetchFn(`${apiUrl}/reports/${encodeURIComponent(id)}/flag`, {
      method: 'POST',
      headers: { [DEVICE_HEADER]: deviceId },
      signal,
    })
    if (!res.ok) throw await httpError(res)
    const { flags } = await res.json()
    if (typeof flags !== 'number') throw new MalformedAnswerError('POST /reports/{id}/flag')
    return { flags }
  })
}

// POST /ask (Ask's spec §5.1). Not retried but for API Gateway's throttle (askPost).
export async function ask(
  apiUrl: string,
  req: { question: string; here?: Here },
  deviceId: string,
  fetchFn: typeof fetch = apiFetch,
): Promise<{ answer: AskAnswer }> {
  const { question } = req
  const body = await askPost(`${apiUrl}/ask`, JSON.stringify({ question, here: hereOf(req.here) }), deviceId, fetchFn)
  return { answer: readAnswer(body.answer, 'POST /ask') }
}

// POST /ask/voice (Ask's spec §5.2): the WAV as base64 in JSON. The audio is only ever in this request's memory.
export async function askVoice(
  apiUrl: string,
  req: { audio: Uint8Array; here?: Here },
  deviceId: string,
  fetchFn: typeof fetch = apiFetch,
): Promise<{ answer: AskAnswer; transcript: string }> {
  const { audio } = req
  const body = await askPost(`${apiUrl}/ask/voice`, JSON.stringify({ audio: base64(audio), here: hereOf(req.here) }), deviceId, fetchFn)
  if (typeof body.transcript !== 'string') throw new MalformedAnswerError('POST /ask/voice')
  return { answer: readAnswer(body.answer, 'POST /ask/voice'), transcript: body.transcript }
}

// Only a location's three fields are sent, as requestUpload sends only its own.
function hereOf(here: Here | undefined): Here | undefined {
  return here === undefined ? undefined : { lat: here.lat, lng: here.lng, accuracyM: here.accuracyM }
}

// Ask's one retry (its spec §4.8): API Gateway's throttling 429, which carries no code, refused the question before it
// was counted. Nothing else is retried, unlike retryOnce: a question_limit or question_cap is shown, a 503 may have
// been counted and paid, and a request lost on the way may have reached the Lambda.
async function askPost(url: string, body: string, deviceId: string, fetchFn: typeof fetch): Promise<Record<string, unknown>> {
  const post = () =>
    withTimeout(ASK_TIMEOUT_MS, async (signal) => {
      const res = await fetchFn(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json', [DEVICE_HEADER]: deviceId },
        body,
        signal,
      })
      if (!res.ok) throw await httpError(res)
      return ((await res.json()) ?? {}) as Record<string, unknown>
    })
  try {
    return await post()
  } catch (err) {
    if (!(err instanceof HttpError && err.status === 429 && err.code === undefined)) throw err
    await new Promise((resolve) => setTimeout(resolve, ASK_THROTTLE_RETRY_MS))
    return post()
  }
}

const ASK_SOURCES: ReadonlySet<unknown> = new Set(['model', 'plain_list'])
const ASK_FALLBACKS: ReadonlySet<unknown> = new Set([
  null,
  'model_calls_paused',
  'deadline',
  'model_error',
  'key_rejected',
  'invalid_answer',
  'no_tool_call',
])
const ASK_KINDS: ReadonlySet<unknown> = new Set([
  'reports',
  'no_reports',
  'place_too_broad',
  'no_place',
  'lookup_unavailable',
  'outside_metro_manila',
  'no_location',
  'off_topic',
  'no_speech',
])
const ASK_VEHICLES: ReadonlySet<unknown> = new Set([null, 'light', 'heavy', 'on_foot'])
const ASK_PLACE_SOURCES: ReadonlySet<unknown> = new Set(['spots', 'nominatim', 'here'])

// The answer's fields, read strictly: anything outside spec §5.3's values is MalformedAnswerError, so no line is
// worded from a value the app doesn't know. A report the app can't word, or a demo pin without its credit, is left
// out, as getPins leaves it off the map (N2); but the deepest one must stay, since the summary is about it (C705).
function readAnswer(value: unknown, route: string): AskAnswer {
  const a = (value ?? {}) as Record<string, unknown>
  const place = a.place as Record<string, unknown> | null | undefined
  const placeOk = place === null || (isText(place?.name) && ASK_PLACE_SOURCES.has(place?.source))
  // A list of reports is always about a place: its summary names it.
  const placed = place !== null || (a.kind !== 'reports' && a.kind !== 'no_reports')
  const lists = [a.reports, a.demo, a.cited, a.suggestions]
  const counts = [a.windowMin, a.radiusM, a.count]
  if (
    !ASK_SOURCES.has(a.source) ||
    !ASK_FALLBACKS.has(a.fallback) ||
    !ASK_KINDS.has(a.kind) ||
    typeof a.crossing !== 'boolean' ||
    !ASK_VEHICLES.has(a.vehicle) ||
    !placeOk ||
    !placed ||
    !lists.every(Array.isArray) ||
    !counts.every((count) => Number.isInteger(count)) ||
    !(a.deepestId === null || typeof a.deepestId === 'string') ||
    !(a.cited as unknown[]).every((id) => typeof id === 'string') ||
    !(a.suggestions as unknown[]).every((name) => typeof name === 'string')
  ) {
    throw new MalformedAnswerError(route)
  }
  const reports = (a.reports as unknown[]).filter((r) => isUsableReport(r, 'live')).map(askReport)
  const demo = (a.demo as unknown[]).filter((r) => isUsableReport(r, 'demo')).map(askReport)
  if (a.deepestId !== null && !reports.some((report) => report.id === a.deepestId)) throw new MalformedAnswerError(route)
  return {
    source: a.source,
    fallback: a.fallback,
    kind: a.kind,
    crossing: a.crossing,
    vehicle: a.vehicle,
    place: place === null ? null : { name: place?.name, source: place?.source },
    windowMin: a.windowMin,
    radiusM: a.radiusM,
    count: a.count,
    reports,
    demo,
    deepestId: a.deepestId,
    cited: a.cited,
    suggestions: a.suggestions,
  } as AskAnswer
}

// A pin the map could show, in its own list, with a distance, a time that parses (or "just now" would claim a fresh
// photo) and a floor mark (or "At least" would be dropped).
function isUsableReport(value: unknown, mode: 'live' | 'demo'): boolean {
  const report = (value ?? {}) as Record<string, unknown>
  return (
    isUsablePin(value) &&
    report.mode === mode &&
    Number.isFinite(report.distanceM) &&
    typeof report.capturedAt === 'string' &&
    Number.isFinite(Date.parse(report.capturedAt)) &&
    typeof report.levelIsFloor === 'boolean'
  )
}

function askReport(value: unknown): AskReport {
  return { ...pick(value, PIN_FIELDS), distanceM: (value as { distanceM: number }).distanceM } as unknown as AskReport
}

// The bytes as standard base64, in chunks, so a 15 s clip's 480 KB never meets the argument limit of a single call.
function base64(bytes: Uint8Array): string {
  let binary = ''
  for (let at = 0; at < bytes.length; at += 0x8000) binary += String.fromCharCode(...bytes.subarray(at, at + 0x8000))
  return btoa(binary)
}

// Runs one request, body included, with a time limit, so a stalled connection fails instead of
// leaving the screen waiting. A caller's `stop` signal cancels it too, with an AbortError. The race
// settles on time even if a fetch ignores the abort.
async function withTimeout<T>(
  timeoutMs: number,
  request: (signal: AbortSignal) => Promise<T>,
  stop?: AbortSignal,
): Promise<T> {
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  let onStop: (() => void) | undefined
  const cut = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort()
      reject(new RequestTimeoutError(timeoutMs))
    }, timeoutMs)
    onStop = () => {
      controller.abort()
      reject(new DOMException('The request was stopped', 'AbortError'))
    }
    if (stop?.aborted) onStop()
    else stop?.addEventListener('abort', onStop, { once: true })
  })
  try {
    return await Promise.race([request(controller.signal), cut])
  } finally {
    clearTimeout(timer)
    if (onStop !== undefined) stop?.removeEventListener('abort', onStop)
  }
}

// A GET to the API whose answer is a JSON object.
async function getJson(url: string, fetchFn: typeof fetch): Promise<Record<string, unknown>> {
  return withTimeout(REQUEST_TIMEOUT_MS, async (signal) => {
    const res = await fetchFn(url, { signal })
    if (!res.ok) throw await httpError(res)
    return (await res.json()) ?? {}
  })
}

async function httpError(res: Response): Promise<HttpError> {
  // S3 answers in XML, so a body that isn't JSON leaves only the status.
  const body: unknown = await res.json().catch(() => undefined)
  const { error, detail } = (body ?? {}) as { error?: unknown; detail?: unknown }
  return new HttpError(
    res.status,
    typeof error === 'string' ? error : undefined,
    typeof detail === 'string' ? detail : undefined,
    retryAfterMs(res.headers.get('retry-after')),
  )
}

// Retry-After as delay-seconds only. An HTTP date isn't read; the poll then waits its interval plus jitter.
function retryAfterMs(value: string | null): number | undefined {
  const seconds = value?.trim()
  return seconds !== undefined && /^\d+$/.test(seconds) ? Number(seconds) * 1000 : undefined
}

// Copies the named fields that are present.
function pick(source: unknown, names: readonly string[]): Record<string, unknown> {
  const from = (source ?? {}) as Record<string, unknown>
  const picked: Record<string, unknown> = {}
  for (const name of names) if (from[name] !== undefined) picked[name] = from[name]
  return picked
}

function isText(value: unknown): value is string {
  return typeof value === 'string' && value.trim() !== ''
}

function isUsablePin(value: unknown): boolean {
  const pin = (value ?? {}) as Record<string, unknown>
  return (
    isText(pin.id) &&
    Number.isFinite(pin.lat) &&
    Number.isFinite(pin.lng) &&
    KNOWN_LEVELS.has(pin.level) &&
    KNOWN_CLASSES.has(pin.passability) &&
    (pin.mode !== 'demo' || isText(pin.credit))
  )
}

// The link POST /uploads gives: a URL and its policy's fields, each a string.
function isPresignedPost(value: unknown): value is PresignedPost {
  const { url, fields } = (value ?? {}) as { url?: unknown; fields?: unknown }
  return (
    typeof url === 'string' &&
    typeof fields === 'object' &&
    fields !== null &&
    !Array.isArray(fields) &&
    Object.values(fields).every((field) => typeof field === 'string')
  )
}

function isUsableSample(value: unknown): boolean {
  const sample = (value ?? {}) as Record<string, unknown>
  const { sampleId, credit, license } = sample
  return (
    isText(sampleId) &&
    isText(credit) &&
    typeof license === 'string' &&
    (SAMPLE_LICENCE.test(license) || license === CONSENTED_LICENCE)
  )
}

function isOverlayData(data: unknown): data is OverlayData {
  const layers = (data ?? {}) as Record<string, unknown>
  return (
    layers.version === 1 &&
    Number.isFinite(layers.width) &&
    Number.isFinite(layers.height) &&
    Array.isArray(layers.water) &&
    Array.isArray(layers.refs)
  )
}
