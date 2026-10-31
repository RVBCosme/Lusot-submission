// Every network answer the end-to-end suite gives (MS5 Task 18). The app is built with VITE_API_URL pointing at
// https://api.e2e.test, so nothing leaves the machine: each request to the API, to the S3 stand-in, and for a map tile is
// answered here through `context.route`, so a popup or a second page is under the same answers as the first. A request to
// any other host that no route answers is refused and fails the test.
//
// The answers' shapes come from app/src/mock/fixtures.ts, the same functions the unit tests' mock API uses, so the suite
// can't drift from them. The photos, overlays and tiles are small synthetic PNGs made here; no photograph is stored.
import { expect, test as base, type BrowserContext, type Route } from '@playwright/test'
import { crc32, deflateSync } from 'node:zlib'
import {
  ASK_TRANSCRIPT,
  askReply,
  isoSeconds,
  levelKeyOf,
  levelLayers,
  MOCK_FILES_ORIGIN,
  pendingBody,
  pinBody,
  pinCapturedAt,
  pinSpecs,
  resultBody,
  sampleList,
  savedSample,
  type Outcome,
  type PinSpec,
  type ReportFacts,
} from '../src/mock/fixtures'

export const API_ORIGIN = 'https://api.e2e.test'
export const FILES_ORIGIN = MOCK_FILES_ORIGIN
const TILE_ORIGIN = 'https://tile.openstreetmap.org'

// The person's own report: the one every upload in the suite makes.
export const OWN_ID = 'r_7f3a9c1e5b2d48f6a0c4e8b1d3f57a92'
// The one live pin the map holds by default: the mock's knee reading, 10 minutes old.
export const LIVE_PIN: PinSpec = pinSpecs()[0]!
// The mock's demo pin: an above-chest reading from 2009, with its credit, place and event (N2).
export const DEMO_PIN: PinSpec = pinSpecs().find((pin) => pin.mode === 'demo')!
// The report a sample's run makes (POST /samples/{sampleId}'s 201).
export const SAMPLE_RUN_ID = 'r_9b8a7c6d5e4f40312a1b2c3d4e5f6a7b'

const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-headers': '*',
  'access-control-allow-methods': 'GET, POST, OPTIONS',
  'access-control-expose-headers': 'retry-after',
}

// What the answers do now. A test changes these between steps.
export interface Behaviour {
  // POST /uploads: a link, or MS1's 503 uploads_paused.
  upload: 'ok' | 'paused'
  // How many reads of the person's own report still answer "processing" before the result; Infinity never answers.
  pendingReads: number
  // What the person's own report ends as (spec §4.2), and its mode: `private` is a photo taken outside Metro Manila.
  outcome: Outcome
  mode: 'live' | 'private'
  // How many of the photo's POSTs to S3 fail as a lost connection before one goes through.
  s3Failures: number
  // How long every answer from the API and the S3 stand-in waits, in ms: a slow network (CDP throttling doesn't slow
  // answers that a route fulfils).
  delayMs: number
  // What GET /map/pins holds. The person's own pin is never in it, as before the API has caught up.
  pins: PinSpec[]
  // How many samples GET /samples lists, or 'error' for a GET /samples that fails.
  sampleCount: number | 'error'
  // POST /samples/{sampleId}: a run (201), the saved result while model calls are paused (200, MS4's C527), or MS1's
  // 503 uploads_paused.
  sampleRun: 'run' | 'saved' | 'paused'
  // What a sample's run reads.
  sampleOutcome: Outcome
}

// One request the app made to the API or the S3 stand-in, for a test to read. The upload's JSON body and the S3 form's
// field names are kept; nothing else of a body is.
export interface Logged {
  method: string
  path: string
  headers: Record<string, string>
  json?: unknown
  formFields?: string[]
}

// A solid-colour PNG, written by hand so the suite needs no image library.
function png(width: number, height: number, [r, g, b]: [number, number, number]): Buffer {
  const row = Buffer.alloc(1 + width * 3)
  for (let x = 0; x < width; x += 1) row.set([r, g, b], 1 + x * 3)
  const raw = Buffer.concat(Array.from({ length: height }, () => row))
  const chunk = (type: string, data: Buffer): Buffer => {
    const head = Buffer.alloc(8)
    head.writeUInt32BE(data.length, 0)
    head.write(type, 4, 'latin1')
    const tail = Buffer.alloc(4)
    tail.writeUInt32BE(crc32(Buffer.concat([head.subarray(4), data])), 0)
    return Buffer.concat([head, data, tail])
  }
  const header = Buffer.alloc(13)
  header.writeUInt32BE(width, 0)
  header.writeUInt32BE(height, 4)
  header.set([8, 2, 0, 0, 0], 8) // 8 bits, RGB, no interlace
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', header),
    chunk('IDAT', deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

const TILE = png(256, 256, [226, 230, 224])
// 4:3, like the layers file's 800 x 600.
const PHOTO = png(400, 300, [108, 128, 138])

export class Mocks {
  readonly behaviour: Behaviour = {
    upload: 'ok',
    pendingReads: 0,
    outcome: { kind: 'level', key: 'knee' },
    mode: 'live',
    s3Failures: 0,
    delayMs: 0,
    pins: [LIVE_PIN],
    sampleCount: 3,
    sampleRun: 'run',
    sampleOutcome: { kind: 'level', key: 'knee' },
  }
  // Requests no route answered: any request to a host outside this machine, and any path the answers don't know.
  readonly unrouted: string[] = []
  readonly requests: Logged[] = []

  private readonly startedAt = Date.now()
  private uploaded = false
  // Each live pin's flag count, as POST /reports/{id}/flag has counted it.
  private readonly flagged = new Map<string, number>()
  private capturedAt: string | undefined
  private gpsAccuracyM: number | undefined
  private gate: Promise<void> | undefined

  private readonly context: BrowserContext

  constructor(context: BrowserContext) {
    this.context = context
  }

  // Holds every POST /uploads until the returned function is called, so a test can look at the "sending" step.
  holdUpload(): () => void {
    let release = () => {}
    this.gate = new Promise<void>((resolve) => {
      release = resolve
    })
    return () => {
      release()
      this.gate = undefined
    }
  }

  async install(): Promise<void> {
    // The last route registered answers first, so this catch-all only sees what no other route took.
    await this.context.route('**/*', (route) => {
      const { hostname } = new URL(route.request().url())
      if (hostname === '127.0.0.1' || hostname === 'localhost') return route.continue()
      this.unrouted.push(`${route.request().method()} ${hostname}`)
      return route.abort('blockedbyclient')
    })
    await this.context.route(`${TILE_ORIGIN}/**`, (route) => route.fulfill({ status: 200, contentType: 'image/png', body: TILE }))
    await this.context.route(`${FILES_ORIGIN}/**`, (route) => this.files(route))
    await this.context.route(`${API_ORIGIN}/**`, (route) => this.api(route))
  }

  private async reply(route: Route, status: number, body?: unknown, headers: Record<string, string> = {}): Promise<void> {
    if (this.behaviour.delayMs > 0) await new Promise((resolve) => setTimeout(resolve, this.behaviour.delayMs))
    return route.fulfill({
      status,
      headers: { ...CORS, ...(body === undefined ? {} : { 'content-type': 'application/json' }), ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  }

  private notFound(route: Route): Promise<void> {
    const { pathname } = new URL(route.request().url())
    this.unrouted.push(`${route.request().method()} ${pathname.replace(/r_[0-9a-f]{32}/g, 'r_…')}`)
    return this.reply(route, 404, { error: 'not_found' })
  }

  private log(route: Route, extra: Partial<Logged> = {}): void {
    const request = route.request()
    const headers = request.headers()
    this.requests.push({
      method: request.method(),
      path: new URL(request.url()).pathname,
      headers: { 'x-lusot-device': headers['x-lusot-device'] ?? '', 'content-type': headers['content-type'] ?? '' },
      ...extra,
    })
  }

  // The links a report carries while its photo is on the map or on its owner's screen (C503).
  private links(id: string) {
    return {
      photoUrl: `${FILES_ORIGIN}/photo/${id}.png`,
      overlayUrl: `${FILES_ORIGIN}/overlay/${id}.png`,
      layersUrl: `${FILES_ORIGIN}/layers/${id}.json`,
    }
  }

  private pinFacts(spec: PinSpec): ReportFacts {
    return {
      reportId: spec.id,
      mode: spec.mode,
      published: true,
      capturedAt: pinCapturedAt(spec, this.startedAt),
      gpsAccuracyM: spec.gpsAccuracyM ?? undefined,
      links: this.links(spec.id),
      demo: spec.demo,
    }
  }

  private ownFacts(): ReportFacts {
    const { mode, outcome } = this.behaviour
    return {
      reportId: OWN_ID,
      mode,
      // Only a level read in Metro Manila is published (MS4's C506, D14).
      published: mode === 'live' && outcome.kind === 'level',
      capturedAt: this.capturedAt ?? isoSeconds(Date.now()),
      gpsAccuracyM: this.gpsAccuracyM,
      links: this.links(OWN_ID),
    }
  }

  // The links a sample's result carries: its photo whatever the outcome (N11), and the overlay with a level.
  private sampleFacts(): ReportFacts {
    return {
      reportId: SAMPLE_RUN_ID,
      mode: 'sample',
      published: false,
      capturedAt: isoSeconds(this.startedAt),
      links: this.links(SAMPLE_RUN_ID),
    }
  }

  private async api(route: Route): Promise<void> {
    const request = route.request()
    const method = request.method()
    const { pathname } = new URL(request.url())
    if (method === 'OPTIONS') return this.reply(route, 204)

    if (method === 'POST' && pathname === '/uploads') {
      let json: unknown
      try {
        json = request.postDataJSON()
      } catch {
        json = undefined
      }
      this.log(route, { json })
      if (this.behaviour.upload === 'paused') return this.reply(route, 503, { error: 'uploads_paused' })
      const body = (json ?? {}) as { capturedAt?: string; gpsAccuracyM?: number }
      this.capturedAt = typeof body.capturedAt === 'string' ? isoSeconds(Date.parse(body.capturedAt)) : undefined
      this.gpsAccuracyM = body.gpsAccuracyM
      await this.gate
      const fields = { 'Content-Type': 'image/jpeg', key: `raw/${OWN_ID}.jpg`, policy: 'e2e-policy', 'x-amz-signature': 'e2e-signature' }
      return this.reply(route, 201, { reportId: OWN_ID, upload: { url: `${FILES_ORIGIN}/uploads/${OWN_ID}`, fields }, expiresInS: 300 })
    }

    if (method === 'GET' && pathname === '/map/pins') {
      this.log(route)
      const pins = this.behaviour.pins.map((spec) =>
        pinBody({ ...spec, capturedAt: pinCapturedAt(spec, this.startedAt) }, spec.flags),
      )
      return this.reply(route, 200, { pins })
    }

    if (method === 'GET' && pathname === '/samples') {
      this.log(route)
      if (this.behaviour.sampleCount === 'error') return this.reply(route, 500, { message: 'Internal Server Error' })
      const samples = sampleList(this.behaviour.sampleCount).map(({ sampleId, credit, license, place, date, event }) => ({
        sampleId,
        credit,
        license,
        place,
        date,
        event,
        photoUrl: `${FILES_ORIGIN}/samples/${sampleId}.png`,
      }))
      return this.reply(route, 200, { samples })
    }

    // Ask Lusot: the dev mock's answer for the question (fixtures.ts's askReply), and for a spoken one, its fixed
    // transcript. The body is kept, so a test can read the question, the location and the clip it sent.
    if (method === 'POST' && (pathname === '/ask' || pathname === '/ask/voice')) {
      const json = (request.postDataJSON() ?? {}) as { question?: string; here?: unknown; audio?: unknown }
      this.log(route, { json })
      const spoken = pathname === '/ask/voice'
      if (spoken && typeof json.audio !== 'string') return this.reply(route, 400, { error: 'bad_audio' })
      const { status, body } = askReply(spoken ? ASK_TRANSCRIPT : String(json.question ?? ''), json.here !== undefined, this.startedAt, Date.now())
      // A limit's 429 says how long until the next UTC hour, as the API's does.
      const wait: Record<string, string> =
        status === 429 ? { 'retry-after': String(Math.ceil((3_600_000 - (Date.now() % 3_600_000)) / 1000)) } : {}
      return this.reply(route, status, status === 200 && spoken ? { ...body, transcript: ASK_TRANSCRIPT } : body, wait)
    }

    // A sample's run (MS4's C512, C527): one POST per tap, which the samples spec counts.
    const sample = /^\/samples\/([A-Za-z0-9_-]+)$/.exec(pathname)
    if (method === 'POST' && sample !== null) {
      this.log(route)
      const spec = sampleList(typeof this.behaviour.sampleCount === 'number' ? this.behaviour.sampleCount : 0).find(
        (candidate) => candidate.sampleId === sample[1],
      )
      if (spec === undefined) return this.reply(route, 404, { error: 'not_found' })
      if (this.behaviour.sampleRun === 'paused') return this.reply(route, 503, { error: 'uploads_paused' })
      if (this.behaviour.sampleRun === 'saved') return this.reply(route, 200, savedSample(spec))
      return this.reply(route, 201, { reportId: SAMPLE_RUN_ID })
    }

    // A flag on a live pin counts once per phone; a demo pin, or one off the map, is not found (MS4's C511, C522).
    const flag = /^\/reports\/([A-Za-z0-9_-]+)\/flag$/.exec(pathname)
    if (method === 'POST' && flag !== null) {
      this.log(route)
      const spec = this.behaviour.pins.find((pin) => pin.id === flag[1])
      if (spec === undefined || spec.mode !== 'live') return this.reply(route, 404, { error: 'not_found' })
      const flags = this.flagged.get(spec.id) ?? spec.flags + 1
      this.flagged.set(spec.id, flags)
      return this.reply(route, 200, { flags })
    }

    const read = /^\/reports\/([A-Za-z0-9_-]+)$/.exec(pathname)
    if (method === 'GET' && read !== null) {
      this.log(route)
      const id = read[1]!
      if (id === OWN_ID) {
        if (!this.uploaded) return this.reply(route, 200, pendingBody('pending', this.ownFacts()))
        if (this.behaviour.pendingReads > 0) {
          this.behaviour.pendingReads -= 1
          return this.reply(route, 200, pendingBody('processing', this.ownFacts()))
        }
        return this.reply(route, 200, resultBody(this.behaviour.outcome, this.ownFacts()))
      }
      if (id === SAMPLE_RUN_ID) return this.reply(route, 200, this.sampleBody())
      const spec = this.behaviour.pins.find((pin) => pin.id === id)
      if (spec !== undefined) return this.reply(route, 200, resultBody({ kind: 'level', key: spec.key }, this.pinFacts(spec)))
      return this.reply(route, 404, { error: 'not_found' })
    }

    return this.notFound(route)
  }

  // A sample run's answer: its outcome, with its photo link whatever the outcome (N11, C637).
  private sampleBody(): Record<string, unknown> {
    const facts = this.sampleFacts()
    const body = resultBody(this.behaviour.sampleOutcome, facts)
    return { photoUrl: facts.links!.photoUrl, ...body }
  }

  private async files(route: Route): Promise<void> {
    const request = route.request()
    const method = request.method()
    const { pathname } = new URL(request.url())
    if (method === 'OPTIONS') return this.reply(route, 204)

    // The photo's POST to S3 (the policy's fields, then the file last). Only the form's field names are kept.
    if (method === 'POST' && pathname === `/uploads/${OWN_ID}`) {
      const body = request.postDataBuffer()?.toString('latin1') ?? ''
      const formFields = [...body.matchAll(/Content-Disposition: form-data; name="([^"]+)"/g)].map((match) => match[1]!)
      this.log(route, { formFields })
      if (this.behaviour.s3Failures > 0) {
        this.behaviour.s3Failures -= 1
        return route.abort('connectionreset')
      }
      this.uploaded = true
      return this.reply(route, 204)
    }

    if (method === 'GET') {
      const layers = /^\/layers\/([A-Za-z0-9_-]+)\.json$/.exec(pathname)
      if (layers !== null) {
        const id = layers[1]!
        const key =
          id === OWN_ID
            ? levelKeyOf(this.behaviour.outcome)
            : id === SAMPLE_RUN_ID
              ? levelKeyOf(this.behaviour.sampleOutcome)
              : this.behaviour.pins.find((pin) => pin.id === id)?.key
        if (key !== undefined) return this.reply(route, 200, levelLayers(key))
      }
      if (/^\/(photo|overlay|samples)\/[A-Za-z0-9_-]+\.png$/.test(pathname)) {
        return route.fulfill({ status: 200, headers: CORS, contentType: 'image/png', body: PHOTO })
      }
    }
    return this.notFound(route)
  }
}

export const test = base.extend<{ mocks: Mocks }>({
  mocks: [
    async ({ context }, provide) => {
      const mocks = new Mocks(context)
      await mocks.install()
      await provide(mocks)
      // Nothing outside the answers' own list was asked for.
      expect(mocks.unrouted, 'requests that no route answered').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }
