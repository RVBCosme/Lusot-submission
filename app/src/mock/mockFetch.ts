// The development mock API (MS5 Task 6, spec C628): a `fetch` that answers MS4's routes from fixtures, so every screen
// is built against every outcome before the real API is wired up. It makes no request: nothing leaves the browser.
// app/src/lib/apiFetch.ts picks it only in a development build with VITE_API_MOCK=1, and a production build holds
// none of it (app/scripts/check-bundle.mjs).
//
// Choosing a state. `scenarioNames()` in fixtures.ts lists every scenario and says what each one does. Pick one with
//   - `?mock=<scenario>` on the page's URL (read when the page loads, so a reload switches it),
//   - else VITE_API_MOCK_SCENARIO in .env.local,
//   - else `level_knee`.
// In a test, pass `createMockFetch({ scenario })` as the client function's `fetchFn`.
//
// The scenario decides what every new report ends as, an upload's or a sample run's. A report goes pending, then
// processing, then final, one step a read, once its photo has been posted (until then it stays pending). The
// seeded pins' times are fixed when the mock is made, so a fresh pin fades as the session goes on. A live report that
// reaches a level joins the pins once its result has been read, as the person's own pin.
import {
  assertScenario,
  DEFAULT_SCENARIO,
  isoSeconds,
  levelHue,
  levelKeyOf,
  levelLayers,
  MOCK_FILES_ORIGIN,
  MOCK_MARKER,
  type LevelKey,
  type Outcome,
  pendingBody,
  pinBody,
  pinCapturedAt,
  pinSpecs,
  type PinSpec,
  resultBody,
  type ReportFacts,
  sampleList,
  sampleScene,
  savedSample,
  scenarioConfig,
  type Scenario,
} from './fixtures'
import { drawOverlay, drawPhoto } from './draw'

export interface MockOptions {
  scenario?: Scenario
  now?: () => number
}

const MARKER_HEADER = 'x-lusot-mock'
const VISIBLE_MS = 3 * 60 * 60_000 // a live pin stays on the map for 3 hours (MS4's Table 14)
const UPLOAD_LINK_MS = 300_000 // the upload link lasts 5 minutes (MS1's C27)
const MAX_AGE_MS = 15 * 60_000 // MS1's W20: the photo was taken at most 15 minutes ago
const MAX_AHEAD_MS = 2 * 60_000 // slack for a phone clock that runs fast
const MAX_ACCURACY_M = 50 // MS4's gps_too_coarse
const MAX_NUDGE_M = 100 // MS4's nudge_too_far
const THROTTLE_RETRY_S = 3
const ISO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/
const REPORT_ID = '(r_[0-9a-f]{32})'

interface MockReport {
  id: string
  outcome: Outcome
  mode: 'live' | 'private' | 'sample'
  published: boolean
  capturedAt: string
  createdAt: number
  lat?: number
  lng?: number
  gpsAccuracyM?: number
  uploaded: boolean
  reads: number
  final: boolean
}

interface UploadFields {
  lat: number
  lng: number
  gpsAccuracyM: number
  capturedMs: number
  nudgeM: number
}

const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)

// MS4's request checks. A string is the 400's detail.
function parseUpload(raw: unknown): UploadFields | string {
  if (typeof raw !== 'string') return 'the body must be JSON'
  let body: Record<string, unknown>
  try {
    body = (JSON.parse(raw) ?? {}) as Record<string, unknown>
  } catch {
    return 'the body is not JSON'
  }
  const { lat, lng, gpsAccuracyM, capturedAt, nudgeM = 0, consentVersion } = body
  if (!isNumber(lat) || !isNumber(lng)) return 'lat and lng must be numbers'
  if (!isNumber(gpsAccuracyM) || gpsAccuracyM < 0) return 'gpsAccuracyM must be a number of metres'
  if (typeof capturedAt !== 'string' || !ISO_TIME.test(capturedAt) || Number.isNaN(Date.parse(capturedAt))) {
    return 'capturedAt must be an ISO 8601 time with a time zone'
  }
  if (!isNumber(nudgeM) || nudgeM < 0) return 'nudgeM must be a number of metres, 0 or more'
  if (typeof consentVersion !== 'string' || consentVersion.trim() === '') return 'consentVersion is missing'
  return { lat, lng, gpsAccuracyM, capturedMs: Date.parse(capturedAt), nudgeM }
}

function newReportId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return `r_${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`
}

// The fields of an upload's policy, which S3 wants back exactly as given.
function uploadFields(reportId: string): Record<string, string> {
  return {
    'Content-Type': 'image/jpeg',
    key: `raw/${reportId}.jpg`,
    policy: 'mock-policy',
    'x-amz-signature': 'mock-signature',
  }
}

function reply(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', [MARKER_HEADER]: MOCK_MARKER, ...headers },
  })
}

// S3 answers in XML; the client reads only the status.
function s3Reply(status: number, code?: string): Response {
  return new Response(code === undefined ? null : `<Error><Code>${code}</Code></Error>`, {
    status,
    headers: { 'content-type': 'application/xml', [MARKER_HEADER]: MOCK_MARKER },
  })
}

function match(path: string, pattern: string): string | undefined {
  return new RegExp(`^${pattern}$`).exec(path)?.[1]
}

export function createMockFetch({ scenario = DEFAULT_SCENARIO, now = Date.now }: MockOptions = {}): typeof fetch {
  assertScenario(scenario)
  const config = scenarioConfig(scenario)
  const startedAt = now()
  const reports = new Map<string, MockReport>()
  const flaggers = new Map<string, Set<string>>()
  const images = new Map<string, string>()
  // `throttled`: API Gateway refuses the first upload request and the first poll, then lets calls through.
  let uploadThrottles = config.uploads === 'throttled' ? 1 : 0
  let pollThrottles = uploadThrottles

  // Each image is drawn once.
  const image = (name: string, make: () => string): string => {
    let url = images.get(name)
    if (url === undefined) {
      url = make()
      images.set(name, url)
    }
    return url
  }

  const linksFor = (key: LevelKey, layersId: string) => ({
    photoUrl: image(`photo:${key}`, () => drawPhoto(levelLayers(key), levelHue(key))),
    overlayUrl: image(`overlay:${key}`, () => drawOverlay(levelLayers(key), levelHue(key))),
    layersUrl: `${MOCK_FILES_ORIGIN}/layers/${layersId}.json`,
  })

  const limited = (code: string): Response => {
    const seconds = Math.ceil((3_600_000 - (now() % 3_600_000)) / 1000)
    return reply(429, { error: code }, { 'retry-after': String(seconds) })
  }
  const throttled = (): Response =>
    reply(429, { message: 'Too Many Requests' }, { 'retry-after': String(THROTTLE_RETRY_S) })

  const paused = (): Response => reply(503, { error: 'uploads_paused' })

  // The answer a limit or the pause gives to an upload or a sample run, or undefined to carry on.
  const refusal = (): Response | undefined => {
    if (config.uploads === 'paused') return paused()
    if (config.uploads === 'device_limit' || config.uploads === 'global_cap') return limited(config.uploads)
    return undefined
  }

  const addReport = (fields: Omit<MockReport, 'id' | 'outcome' | 'reads' | 'final'>): MockReport => {
    const report: MockReport = { ...fields, id: newReportId(), outcome: config.outcome, reads: 0, final: false }
    reports.set(report.id, report)
    return report
  }

  const createUpload = (body: unknown): Response => {
    if (uploadThrottles > 0) {
      uploadThrottles -= 1
      return throttled()
    }
    // The pause is the first thing MS1's upload route checks; the limits come after the request's own checks.
    if (config.uploads === 'paused') return paused()
    const request = parseUpload(body)
    if (typeof request === 'string') return reply(400, { error: 'bad_request', detail: request })
    if (request.gpsAccuracyM > MAX_ACCURACY_M) return reply(422, { error: 'gps_too_coarse' })
    if (request.nudgeM > MAX_NUDGE_M) return reply(422, { error: 'nudge_too_far' })
    const at = now()
    if (at - request.capturedMs > MAX_AGE_MS) return reply(422, { error: 'capture_too_old' })
    if (request.capturedMs - at > MAX_AHEAD_MS) return reply(422, { error: 'capture_in_future' })
    const refused = refusal()
    if (refused !== undefined) return refused

    const report = addReport({
      mode: config.mode,
      published: config.mode === 'live' && config.outcome.kind === 'level',
      capturedAt: isoSeconds(request.capturedMs),
      createdAt: at,
      lat: request.lat,
      lng: request.lng,
      gpsAccuracyM: request.gpsAccuracyM,
      uploaded: false,
    })
    const upload = { url: `${MOCK_FILES_ORIGIN}/uploads/${report.id}`, fields: uploadFields(report.id) }
    return reply(201, { reportId: report.id, upload, expiresInS: 300 })
  }

  // The photo's POST to S3: the policy's fields as given, then the file last, within 5 minutes.
  const postPhoto = (id: string, body: unknown): Response => {
    const report = reports.get(id)
    if (report === undefined) return s3Reply(404, 'NoSuchKey')
    if (!(body instanceof FormData)) return s3Reply(400, 'InvalidArgument')
    if (now() - report.createdAt > UPLOAD_LINK_MS) return s3Reply(403, 'AccessDenied')
    const entries: [string, unknown][] = []
    body.forEach((value, name) => entries.push([name, value]))
    const last = entries.pop()
    if (last === undefined || last[0] !== 'file') return s3Reply(400, 'InvalidArgument')
    const given = JSON.stringify(entries.sort(([a], [b]) => a.localeCompare(b)))
    const expected = JSON.stringify(Object.entries(uploadFields(id)).sort(([a], [b]) => a.localeCompare(b)))
    if (given !== expected) return s3Reply(403, 'AccessDenied')
    report.uploaded = true
    return s3Reply(204)
  }

  const factsOf = (report: MockReport): ReportFacts => ({
    reportId: report.id,
    mode: report.mode,
    published: report.published,
    capturedAt: report.capturedAt,
    gpsAccuracyM: report.gpsAccuracyM,
    links: report.outcome.kind === 'level' ? linksFor(report.outcome.key, report.id) : undefined,
  })

  const pinFacts = (spec: PinSpec): ReportFacts => {
    const visible = spec.mode === 'demo' || now() - Date.parse(pinCapturedAt(spec, startedAt)) < VISIBLE_MS
    return {
      reportId: spec.id,
      mode: spec.mode,
      published: true,
      capturedAt: pinCapturedAt(spec, startedAt),
      gpsAccuracyM: spec.gpsAccuracyM ?? undefined,
      links: visible ? linksFor(spec.key, spec.id) : undefined,
      demo: spec.demo,
    }
  }

  const readReport = (id: string): Response => {
    if (pollThrottles > 0) {
      pollThrottles -= 1
      return throttled()
    }
    const report = reports.get(id)
    if (report !== undefined) {
      const facts = factsOf(report)
      if (!report.uploaded) return reply(200, pendingBody('pending', facts))
      report.reads += 1
      if (report.reads === 1) return reply(200, pendingBody('pending', facts))
      if (report.reads === 2 || report.outcome.kind === 'pending') return reply(200, pendingBody('processing', facts))
      report.final = true
      return reply(200, resultBody(report.outcome, facts))
    }
    const spec = pinSpecs().find((candidate) => candidate.id === id)
    if (spec !== undefined) return reply(200, resultBody({ kind: 'level', key: spec.key }, pinFacts(spec)))
    return reply(404, { error: 'not_found' })
  }

  const flagsOf = (id: string, base: number): number => base + (flaggers.get(id)?.size ?? 0)

  // The person's own live reports that are on the map: a level, read, within 3 hours.
  const ownPins = (): Record<string, unknown>[] =>
    [...reports.values()].flatMap((report) => {
      const key = levelKeyOf(report.outcome)
      if (key === undefined || !report.final || !report.published) return []
      if (now() - Date.parse(report.capturedAt) >= VISIBLE_MS) return []
      return [
        pinBody(
          {
            id: report.id,
            lat: Math.round((report.lat ?? 0) * 1e4) / 1e4, // 4 decimals (MS4's C514)
            lng: Math.round((report.lng ?? 0) * 1e4) / 1e4,
            capturedAt: report.capturedAt,
            mode: 'live',
            gpsAccuracyM: report.gpsAccuracyM ?? null,
            key,
          },
          flagsOf(report.id, 0),
        ),
      ]
    })

  const readPins = (): Response => {
    const seeded = config.pins
      ? pinSpecs().map((spec) =>
          pinBody({ ...spec, capturedAt: pinCapturedAt(spec, startedAt) }, flagsOf(spec.id, spec.flags)),
        )
      : []
    return reply(200, { pins: [...seeded, ...ownPins()] })
  }

  // The count a pin has so far, if it can be flagged: live, and still on the map.
  const flaggableBase = (id: string): number | undefined => {
    const spec = config.pins ? pinSpecs().find((candidate) => candidate.id === id) : undefined
    if (spec !== undefined) {
      const onMap = spec.mode === 'live' && now() - Date.parse(pinCapturedAt(spec, startedAt)) < VISIBLE_MS
      return onMap ? spec.flags : undefined
    }
    return ownPins().some((pin) => pin.id === id) ? 0 : undefined
  }

  const flag = (id: string, device: string): Response => {
    const base = flaggableBase(id)
    if (base === undefined) return reply(404, { error: 'not_found' })
    const devices = flaggers.get(id) ?? new Set<string>()
    devices.add(device)
    flaggers.set(id, devices)
    return reply(200, { flags: flagsOf(id, base) })
  }

  const listSamples = (): Response =>
    reply(200, {
      samples: sampleList(config.sampleCount).map((sample) => {
        const { sampleId, credit, license, place, date, event } = sample
        const { layers, hue } = sampleScene(sample)
        const photoUrl = image(`sample:${sampleId}`, () => drawPhoto(layers, hue))
        return { sampleId, credit, license, place, date, event, photoUrl }
      }),
    })

  const runSample = (sampleId: string): Response => {
    const refused = refusal()
    if (refused !== undefined) return refused
    const sample = sampleList(config.sampleCount).find((candidate) => candidate.sampleId === sampleId)
    if (sample === undefined) return reply(404, { error: 'not_found' })
    if (config.savedSamples) return reply(200, savedSample(sample))
    const at = now()
    const report = addReport({
      mode: 'sample',
      published: false,
      capturedAt: isoSeconds(at),
      createdAt: at,
      uploaded: true,
    })
    return reply(201, { reportId: report.id })
  }

  const layersFile = (id: string): Response => {
    const outcome = reports.get(id)?.outcome
    const key = outcome === undefined ? pinSpecs().find((spec) => spec.id === id)?.key : levelKeyOf(outcome)
    return key === undefined ? reply(404, { error: 'not_found' }) : reply(200, levelLayers(key))
  }

  return async (input, init) => {
    if (init?.signal?.aborted) throw new DOMException('The request was stopped', 'AbortError')
    const request = input instanceof Request ? input : undefined
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url)
    const method = (init?.method ?? request?.method ?? 'GET').toUpperCase()
    const path = url.pathname

    if (url.origin === MOCK_FILES_ORIGIN) {
      const photoFor = match(path, `/uploads/${REPORT_ID}`)
      if (method === 'POST' && photoFor !== undefined) return postPhoto(photoFor, init?.body)
      const layersFor = match(path, `/layers/${REPORT_ID}\\.json`)
      if (method === 'GET' && layersFor !== undefined) return layersFile(layersFor)
      return reply(404, { error: 'not_found' })
    }

    const device = new Headers(init?.headers ?? request?.headers).get('x-lusot-device') ?? 'none'
    if (method === 'POST' && path === '/uploads') return createUpload(init?.body)
    if (method === 'GET' && path === '/map/pins') return readPins()
    if (method === 'GET' && path === '/samples') return listSamples()
    const sampleId = match(path, '/samples/([^/]+)')
    if (method === 'POST' && sampleId !== undefined) return runSample(decodeURIComponent(sampleId))
    const reportId = match(path, `/reports/([^/]+)`)
    if (method === 'GET' && reportId !== undefined) return readReport(decodeURIComponent(reportId))
    const flagged = match(path, `/reports/([^/]+)/flag`)
    if (method === 'POST' && flagged !== undefined) return flag(decodeURIComponent(flagged), device)
    return reply(404, { error: 'not_found' })
  }
}

// The scenario a page asks for: `?mock=<scenario>`, else VITE_API_MOCK_SCENARIO, else the default. An unknown
// name throws, listing the ones there are.
export function pickScenario(search: string, fromEnv: string | undefined): Scenario {
  const name = new URLSearchParams(search).get('mock') || fromEnv || DEFAULT_SCENARIO
  assertScenario(name)
  return name
}

let shared: typeof fetch | undefined

// The one mock a development page uses, made on its first request. An arrow function, so loading this module runs
// nothing and a production build can drop it.
export const mockFetch: typeof fetch = (input, init) => {
  shared ??= createMockFetch({
    scenario: pickScenario(
      typeof location === 'undefined' ? '' : location.search,
      import.meta.env.VITE_API_MOCK_SCENARIO,
    ),
  })
  return shared(input, init)
}
