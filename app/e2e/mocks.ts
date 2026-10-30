// Every network answer the end-to-end suite gives (MS5 Task 18). The app is built with VITE_API_URL pointing at
// https://api.e2e.test, so nothing leaves the machine: each request to the API, to the S3 stand-in, and for a map tile is
// answered here through `page.route`. A request to any other host that no route answers is refused and fails the test.
//
// The answers' shapes come from app/src/mock/fixtures.ts, the same functions the unit tests' mock API uses, so the suite
// can't drift from them. The photos, overlays and tiles are small synthetic PNGs made here; no photograph is stored.
import { expect, test as base, type Page, type Route } from '@playwright/test'
import { crc32, deflateSync } from 'node:zlib'
import {
  isoSeconds,
  levelLayers,
  MOCK_FILES_ORIGIN,
  pendingBody,
  pinBody,
  pinCapturedAt,
  pinSpecs,
  resultBody,
  sampleList,
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
  // What GET /map/pins holds. The person's own pin is never in it, as before the API has caught up.
  pins: PinSpec[]
  // How many samples GET /samples lists.
  sampleCount: number
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
  readonly behaviour: Behaviour = { upload: 'ok', pendingReads: 0, pins: [LIVE_PIN], sampleCount: 3 }
  // Requests no route answered: any request to a host outside this machine, and any path the answers don't know.
  readonly unrouted: string[] = []
  readonly requests: Logged[] = []

  private readonly startedAt = Date.now()
  private uploaded = false
  private capturedAt: string | undefined
  private gpsAccuracyM: number | undefined
  private gate: Promise<void> | undefined

  private readonly page: Page

  constructor(page: Page) {
    this.page = page
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
    await this.page.route('**/*', (route) => {
      const { hostname } = new URL(route.request().url())
      if (hostname === '127.0.0.1' || hostname === 'localhost') return route.continue()
      this.unrouted.push(`${route.request().method()} ${hostname}`)
      return route.abort('blockedbyclient')
    })
    await this.page.route(`${TILE_ORIGIN}/**`, (route) => route.fulfill({ status: 200, contentType: 'image/png', body: TILE }))
    await this.page.route(`${FILES_ORIGIN}/**`, (route) => this.files(route))
    await this.page.route(`${API_ORIGIN}/**`, (route) => this.api(route))
  }

  private reply(route: Route, status: number, body?: unknown, headers: Record<string, string> = {}): Promise<void> {
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
    return {
      reportId: OWN_ID,
      mode: 'live',
      published: true,
      capturedAt: this.capturedAt ?? isoSeconds(Date.now()),
      gpsAccuracyM: this.gpsAccuracyM,
      links: this.links(OWN_ID),
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
        return this.reply(route, 200, resultBody({ kind: 'level', key: 'knee' }, this.ownFacts()))
      }
      const spec = this.behaviour.pins.find((pin) => pin.id === id)
      if (spec !== undefined) return this.reply(route, 200, resultBody({ kind: 'level', key: spec.key }, this.pinFacts(spec)))
      return this.reply(route, 404, { error: 'not_found' })
    }

    return this.notFound(route)
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
      this.uploaded = true
      return this.reply(route, 204)
    }

    if (method === 'GET') {
      const layers = /^\/layers\/([A-Za-z0-9_-]+)\.json$/.exec(pathname)
      if (layers !== null) {
        const id = layers[1]!
        const key = id === OWN_ID ? 'knee' : this.behaviour.pins.find((pin) => pin.id === id)?.key
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
    async ({ page }, provide) => {
      const mocks = new Mocks(page)
      await mocks.install()
      await provide(mocks)
      // Nothing outside the answers' own list was asked for.
      expect(mocks.unrouted, 'requests that no route answered').toEqual([])
    },
    { auto: true },
  ],
})

export { expect }
