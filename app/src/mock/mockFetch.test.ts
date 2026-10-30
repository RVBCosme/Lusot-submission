// The development mock, read the way the app reads it: every answer goes through Task 5's real client functions
// (api.ts, poll.ts, retry.ts), so a state the mock gives is a state the screens can show.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FAILED_REASONS, PASSABILITY, REFUSED_REASONS } from '../copy/levels'
import {
  flagPin,
  getLayers,
  getPins,
  getReport,
  getSamples,
  HttpError,
  postToS3,
  requestUpload,
  runSample,
  type OverlayData,
  type ReportResult,
} from '../lib/api'
import { pollReport, PollTimeoutError } from '../lib/poll'
import { retryOnce } from '../lib/retry'
import { MOCK_FILES_ORIGIN, MOCK_MARKER, scenarioNames, type Scenario } from './fixtures'
import { createMockFetch, pickScenario } from './mockFetch'

const API = 'https://mock.invalid'
const DEVICE = '0f8e4a52-3c1d-4b7a-9e26-5d0c8b1f7a43'
const OTHER_DEVICE = '7a1d3c55-9b0e-4f24-8c61-2e5f0a9d4b38'
const NOW = Date.parse('2026-10-30T10:20:00Z')
const REPORT_ID = /^r_[0-9a-f]{32}$/
const JPEG = new Blob(['jpeg bytes'], { type: 'image/jpeg' })
const REQ = {
  lat: 14.6095,
  lng: 120.9894,
  gpsAccuracyM: 12,
  capturedAt: new Date(NOW - 60_000).toISOString(),
  nudgeM: 18,
  consentVersion: '3f9a1c07',
}

afterEach(() => {
  vi.restoreAllMocks()
})

// A clock the poll and the mock share: sleeping moves it, so a 10-minute window takes no time.
function clock(start = NOW) {
  let t = start
  const waits: number[] = []
  return {
    now: () => t,
    sleep: async (ms: number) => {
      waits.push(ms)
      t += ms
    },
    waits,
    advance: (ms: number) => {
      t += ms
    },
  }
}

function mockWith(scenario?: Scenario, c = clock()) {
  return { fetchFn: createMockFetch({ scenario, now: c.now }), c }
}

// The whole trip a photo takes: the upload link, the photo to S3, then the poll to a final status.
async function takePhoto(scenario?: Scenario, req = REQ) {
  const { fetchFn, c } = mockWith(scenario)
  const { reportId, upload } = await requestUpload(API, req, DEVICE, fetchFn)
  await postToS3(upload, JPEG, fetchFn)
  const result = await pollReport(API, reportId, { fetchFn, sleep: c.sleep, now: c.now })
  return { fetchFn, c, reportId, result }
}

async function levelReport(scenario: Scenario): Promise<ReportResult> {
  return (await takePhoto(scenario)).result
}

describe('a level reading', () => {
  it('is the default: knee, read from geometry, with inches and a dropped reference', async () => {
    const { result, reportId } = await takePhoto()
    expect(result).toMatchObject({
      reportId,
      status: 'done',
      mode: 'live',
      published: true,
      noFloodSeen: false,
      level: 'knee',
      landmark: 'rim_three_quarters',
      passability: 'NPLV',
      levelIsFloor: false,
      levelFrom: 'geometry',
      depthInMin: 15,
      depthInMax: 18,
      basis: { vehicles: 1, people: 1 },
      gpsAccuracyM: 12,
    })
    expect(reportId).toMatch(REPORT_ID)
    expect(result.capturedAt).toBe('2026-10-30T10:19:00Z')
    expect(result.readings).toHaveLength(3)
    const dropped = result.readings?.filter((reading) => reading.dropped !== null)
    expect(dropped).toEqual([
      {
        id: 3,
        kind: 'person',
        landmark: null,
        level: null,
        levelIsFloor: null,
        inches: null,
        used: false,
        dropped: 'person_not_adult',
      },
    ])
    // C507: inches only on a deciding reading whose level came from geometry.
    expect(result.readings?.map((reading) => reading.inches)).toEqual([[15, 18], undefined, null])
  })

  it('links a photo and an overlay it draws, and a layers file in MS4\'s C524 shape', async () => {
    const { result, fetchFn } = await takePhoto()
    expect(result.photoUrl).toMatch(/^data:image\//)
    expect(result.overlayUrl).toMatch(/^data:image\//)
    expect(result.layersUrl?.startsWith(`${MOCK_FILES_ORIGIN}/`)).toBe(true)
    const layers = await getLayers(result.layersUrl ?? '', fetchFn)
    expect(layers).toBeDefined()
    const { version, width, height, water, refs } = layers as OverlayData
    expect(version).toBe(1)
    expect(width).toBeGreaterThan(0)
    expect(height).toBeGreaterThan(0)
    expect(water.length).toBeGreaterThan(0)
    expect(refs.map((ref) => ref.id)).toEqual([1, 2, 3])
    // One dropped reference: its cause kept, its level and level_from null, and no waterline or rim.
    const dropped = refs.filter((ref) => ref.dropped !== null)
    expect(dropped).toHaveLength(1)
    expect(dropped[0]).toMatchObject({
      id: 3,
      kind: 'person',
      level: null,
      level_from: null,
      level_is_floor: null,
      landmark: null,
      used: false,
      dropped: 'person_not_adult',
      rim: null,
      rim_outline: null,
      waterline: null,
    })
    // Every ref carries every C524 field, as nulls rather than missing ones.
    for (const ref of refs) {
      expect(Object.keys(ref).sort()).toEqual(
        [
          'id', 'kind', 'box', 'outline', 'landmark', 'level', 'level_from', 'level_is_floor', 'used', 'dropped',
          'rechecked', 'rim_outline', 'rim', 'waterline',
        ].sort(),
      )
      expect(ref.box).toHaveLength(4)
    }
    // The wheel was read from geometry: its fitted rim and waterline are there.
    expect(refs[0]).toMatchObject({ kind: 'wheel', level: 'knee', level_from: 'geometry', used: true, rechecked: true })
    expect(refs[0].rim?.center).toHaveLength(2)
    expect(refs[0].waterline).toHaveLength(2)
  })

  it('has readings and layers that agree, reference by reference', async () => {
    const { result, fetchFn } = await takePhoto()
    const layers = (await getLayers(result.layersUrl ?? '', fetchFn)) as OverlayData
    for (const reading of result.readings ?? []) {
      const ref = layers.refs.find((candidate) => candidate.id === reading.id)
      expect(ref, `reference ${reading.id}`).toBeDefined()
      expect(ref).toMatchObject({
        kind: reading.kind,
        landmark: reading.landmark,
        level: reading.level,
        level_is_floor: reading.levelIsFloor,
        used: reading.used,
        dropped: reading.dropped,
      })
    }
  })

  it("carries MS4's floor keys: true on a floor reading, false on an exact one, null where there is no level", async () => {
    const knee = await levelReport('level_knee')
    expect(knee.readings?.map((reading) => reading.levelIsFloor)).toEqual([false, false, null])
    const floor = await levelReport('level_floor')
    expect(floor.readings?.map((reading) => reading.levelIsFloor)).toEqual([true])
    const { fetchFn, result } = await takePhoto('level_floor')
    const layers = (await getLayers(result.layersUrl ?? '', fetchFn)) as OverlayData
    expect(layers.refs.map((ref) => ref.level_is_floor)).toEqual([true])
  })

  it('moves from pending to processing to done, one step a poll, once the photo has been posted', async () => {
    const { fetchFn } = mockWith()
    const { reportId, upload } = await requestUpload(API, REQ, DEVICE, fetchFn)
    // No photo yet: still pending however often it is read.
    for (let i = 0; i < 4; i++) expect((await getReport(API, reportId, fetchFn))?.status).toBe('pending')
    await postToS3(upload, JPEG, fetchFn)
    const statuses: string[] = []
    for (let i = 0; i < 4; i++) statuses.push((await getReport(API, reportId, fetchFn))?.status ?? '404')
    expect(statuses).toEqual(['pending', 'processing', 'done', 'done'])
  })

  it('is pending with no level fields as soon as it is made', async () => {
    const { fetchFn } = mockWith()
    const { reportId } = await requestUpload(API, REQ, DEVICE, fetchFn)
    const report = await getReport(API, reportId, fetchFn)
    expect(report).toMatchObject({ reportId, status: 'pending', mode: 'live', published: false })
    expect(report?.level).toBeUndefined()
    expect(report?.photoUrl).toBeUndefined()
  })

  it.each([
    ['level_landmark', 'half_tire', 'hub', false, 'landmark'],
    ['level_floor', 'tire', 'wheel_covered', true, 'landmark'],
    ['level_below_gutter', 'below_gutter', 'tire_only', false, 'landmark'],
    ['level_above_chest', 'above_chest', 'above_chest', false, 'landmark'],
  ] as const)('%s reads %s from %s', async (scenario, level, landmark, floor, from) => {
    const result = await levelReport(scenario)
    expect(result).toMatchObject({
      status: 'done',
      noFloodSeen: false,
      level,
      landmark,
      levelIsFloor: floor,
      levelFrom: from,
      passability: PASSABILITY[level],
    })
    // Inches come only from geometry, which these four don't use.
    expect(result.depthInMin).toBeUndefined()
    expect(result.depthInMax).toBeUndefined()
    expect(result.readings?.every((reading) => reading.inches === undefined || reading.inches === null)).toBe(true)
    expect(result.photoUrl).toMatch(/^data:image\//)
  })

  it('level_private is the same reading taken outside Metro Manila: private, never published', async () => {
    const { result, fetchFn } = await takePhoto('level_private')
    expect(result).toMatchObject({ status: 'done', level: 'knee', mode: 'private', published: false })
    expect(result.photoUrl).toMatch(/^data:image\//)
    // It never reaches the map.
    expect((await getPins(API, fetchFn)).some((pin) => pin.id === result.reportId)).toBe(false)
  })
})

describe('the other outcomes', () => {
  it('no_flood_seen: done, with noFloodSeen and nothing else', async () => {
    const result = await levelReport('no_flood_seen')
    expect(result).toMatchObject({ status: 'done', noFloodSeen: true, mode: 'live', published: false })
    const levelFields = ['level', 'landmark', 'passability', 'basis', 'readings', 'photoUrl', 'overlayUrl', 'layersUrl']
    for (const field of levelFields) expect(result, field).not.toHaveProperty(field)
  })

  it.each(REFUSED_REASONS)('refused_%s is a refusal for that reason', async (reason) => {
    const result = await levelReport(`refused_${reason}`)
    expect(result).toMatchObject({ status: 'refused', refusalReason: reason, published: false })
    expect(result).not.toHaveProperty('level')
    expect(result).not.toHaveProperty('noFloodSeen')
  })

  it.each(FAILED_REASONS)('failed_%s is a failure for that reason', async (reason) => {
    const result = await levelReport(`failed_${reason}`)
    expect(result).toMatchObject({ status: 'failed', refusalReason: reason, published: false })
    expect(result).not.toHaveProperty('level')
  })

  it('pending_forever never ends: the poll gives up at its 10 minutes with PollTimeoutError', async () => {
    const { fetchFn, c } = mockWith('pending_forever')
    const { reportId, upload } = await requestUpload(API, REQ, DEVICE, fetchFn)
    await postToS3(upload, JPEG, fetchFn)
    const poll = pollReport(API, reportId, { fetchFn, sleep: c.sleep, now: c.now })
    await expect(poll).rejects.toBeInstanceOf(PollTimeoutError)
    expect(c.now() - NOW).toBe(600_000)
    expect((await getReport(API, reportId, fetchFn))?.status).toBe('processing')
  })
})

describe('the limits and the pause', () => {
  it.each(['device_limit', 'global_cap'] as const)('%s is a 429 with its code and the next hour', async (scenario) => {
    const { fetchFn } = mockWith(scenario)
    const error = await requestUpload(API, REQ, DEVICE, fetchFn).catch((err: unknown) => err)
    expect(error).toBeInstanceOf(HttpError)
    expect(error).toMatchObject({ status: 429, code: scenario, isDeviceLimit: true, retryAfterMs: 2_400_000 })
    // A sample run is refused the same way.
    await expect(runSample(API, 'sample-01', DEVICE, fetchFn)).rejects.toMatchObject({ status: 429, code: scenario })
  })

  it('a limit is never retried', async () => {
    const { fetchFn } = mockWith('device_limit')
    const call = vi.fn(() => requestUpload(API, REQ, DEVICE, fetchFn))
    await expect(retryOnce(call, { sleep: async () => {} })).rejects.toMatchObject({ code: 'device_limit' })
    expect(call).toHaveBeenCalledOnce()
  })

  it('throttled: a code-less 429 with a Retry-After on the first upload request, then it goes through', async () => {
    const { fetchFn } = mockWith('throttled')
    await expect(requestUpload(API, REQ, DEVICE, fetchFn)).rejects.toMatchObject({
      status: 429,
      code: undefined,
      isDeviceLimit: false,
      retryAfterMs: 3000,
    })
    const second = await requestUpload(API, REQ, DEVICE, fetchFn)
    expect(second.reportId).toMatch(REPORT_ID)
  })

  it('throttled is retried once by retryOnce, since it carries no code', async () => {
    const { fetchFn } = mockWith('throttled')
    const sleep = vi.fn(async () => {})
    const made = await retryOnce(() => requestUpload(API, REQ, DEVICE, fetchFn), { sleep })
    expect(sleep).toHaveBeenCalledWith(2000)
    expect(made.reportId).toMatch(REPORT_ID)
  })

  it('throttled also answers the first poll with a 429 that the poll waits out for its Retry-After', async () => {
    const { fetchFn, c } = mockWith('throttled')
    const noWait = { sleep: async () => {} }
    const { reportId, upload } = await retryOnce(() => requestUpload(API, REQ, DEVICE, fetchFn), noWait)
    await postToS3(upload, JPEG, fetchFn)
    const result = await pollReport(API, reportId, { fetchFn, sleep: c.sleep, now: c.now })
    expect(result.status).toBe('done')
    // 3 s from the 429's Retry-After (more than the 2 s interval), then the interval for the two steps before done.
    expect(c.waits).toEqual([3000, 2000, 2000])
  })

  it('uploads_paused: a 503 on an upload and on a sample run, never retried', async () => {
    const { fetchFn } = mockWith('uploads_paused')
    const call = vi.fn(() => requestUpload(API, REQ, DEVICE, fetchFn))
    const paused = { status: 503, code: 'uploads_paused' }
    await expect(retryOnce(call, { sleep: async () => {} })).rejects.toMatchObject(paused)
    expect(call).toHaveBeenCalledOnce()
    await expect(runSample(API, 'sample-01', DEVICE, fetchFn)).rejects.toMatchObject(paused)
  })

  it('failed_model_calls_paused: the report ends failed, and a sample run answers its saved result', async () => {
    const { result, fetchFn } = await takePhoto('failed_model_calls_paused')
    expect(result).toMatchObject({ status: 'failed', refusalReason: 'model_calls_paused' })
    const samples = await getSamples(API, fetchFn)
    const saved = await Promise.all(samples.map((sample) => runSample(API, sample.sampleId, DEVICE, fetchFn)))
    for (const answer of saved) {
      expect(answer).toMatchObject({ saved: true })
      expect(answer).not.toHaveProperty('reportId')
    }
    expect(saved[0]).toEqual({
      saved: true,
      savedAt: '2026-10-29T14:20:00Z',
      result: {
        status: 'done',
        noFloodSeen: false,
        level: 'knee',
        landmark: 'rim_three_quarters',
        passability: 'NPLV',
        levelIsFloor: false,
      },
    })
    // A seeding run's "no flood seen" is saved too, and carries no level fields.
    expect(saved[1]).toEqual({
      saved: true,
      savedAt: '2026-10-29T14:20:00Z',
      result: { status: 'done', noFloodSeen: true },
    })
  })
})

describe('upload checks', () => {
  it.each([
    ['gps_too_coarse', { ...REQ, gpsAccuracyM: 60 }],
    ['nudge_too_far', { ...REQ, nudgeM: 101 }],
    ['capture_too_old', { ...REQ, capturedAt: new Date(NOW - 16 * 60_000).toISOString() }],
    ['capture_in_future', { ...REQ, capturedAt: new Date(NOW + 3 * 60_000).toISOString() }],
  ])('a request MS4 refuses with %s is refused with a 422', async (code, request) => {
    const { fetchFn } = mockWith()
    await expect(requestUpload(API, request, DEVICE, fetchFn)).rejects.toMatchObject({ status: 422, code })
  })

  it.each([
    ['no coordinates', { ...REQ, lat: Number.NaN }],
    ['no time zone on the time', { ...REQ, capturedAt: '2026-10-30T10:19:00' }],
    ['a negative nudge', { ...REQ, nudgeM: -1 }],
    ['no consent version', { ...REQ, consentVersion: '' }],
  ])('a request with %s is a 400 bad_request', async (_name, request) => {
    const { fetchFn } = mockWith()
    const badRequest = { status: 400, code: 'bad_request' }
    await expect(requestUpload(API, request, DEVICE, fetchFn)).rejects.toMatchObject(badRequest)
  })

  it('a request that is not JSON is a 400 too', async () => {
    const { fetchFn } = mockWith()
    const res = await fetchFn(`${API}/uploads`, { method: 'POST', body: 'not json' })
    expect(res.status).toBe(400)
  })

  it('gives the link S3 would: the photo goes last, the policy\'s fields as given, within 5 minutes', async () => {
    const { fetchFn, c } = mockWith()
    const { upload } = await requestUpload(API, REQ, DEVICE, fetchFn)
    expect(upload.fields['Content-Type']).toBe('image/jpeg')

    // The photo before the fields: S3 ignores what follows the file, so the policy is then missing.
    const fileFirst = new FormData()
    fileFirst.append('file', JPEG)
    for (const [name, value] of Object.entries(upload.fields)) fileFirst.append(name, value)
    expect((await fetchFn(upload.url, { method: 'POST', body: fileFirst })).status).toBe(400)

    // Fields left out.
    await expect(postToS3({ url: upload.url, fields: {} }, JPEG, fetchFn)).rejects.toMatchObject({ status: 403 })

    // A link that isn't one the mock gave.
    const stranger = { url: `${MOCK_FILES_ORIGIN}/uploads/r_${'0'.repeat(32)}`, fields: upload.fields }
    await expect(postToS3(stranger, JPEG, fetchFn)).rejects.toMatchObject({ status: 404 })

    // Past its 5 minutes.
    c.advance(301_000)
    await expect(postToS3(upload, JPEG, fetchFn)).rejects.toMatchObject({ status: 403 })
  })

  it('answers the S3 post with 204 and an empty body', async () => {
    const { fetchFn } = mockWith()
    const { upload } = await requestUpload(API, REQ, DEVICE, fetchFn)
    const form = new FormData()
    for (const [name, value] of Object.entries(upload.fields)) form.append(name, value)
    form.append('file', JPEG)
    const res = await fetchFn(upload.url, { method: 'POST', body: form })
    expect(res.status).toBe(204)
    expect(await res.text()).toBe('')
  })
})

describe('samples', () => {
  it('lists three by default, each credited and licensed on the allow-list, with a photo it draws', async () => {
    const { fetchFn } = mockWith()
    const samples = await getSamples(API, fetchFn)
    expect(samples).toHaveLength(3)
    expect(samples.map((sample) => sample.license)).toEqual(['CC0 1.0', 'CC BY 4.0', 'used with permission'])
    for (const sample of samples) {
      expect(sample.sampleId).toMatch(/^sample-\d\d$/)
      expect(sample.credit.length).toBeGreaterThan(0)
      expect(sample.photoUrl).toMatch(/^data:image\//)
    }
    expect(samples[0]).toMatchObject({ place: 'Marikina', date: '2009-09-26', event: 'Typhoon Ondoy' })
    expect(samples[2].event).toBeUndefined()
  })

  it.each([
    ['samples_none', 0],
    ['samples_one', 1],
    ['samples_two', 2],
  ] as const)('%s lists %i', async (scenario, count) => {
    const { fetchFn } = mockWith(scenario)
    const raw = (await (await fetchFn(`${API}/samples`)).json()) as { samples: unknown[] }
    expect(raw.samples).toHaveLength(count)
    expect(await getSamples(API, fetchFn)).toHaveLength(count)
  })

  it('a sample run starts a paid run, never a pin: sample mode, not published, the scenario outcome', async () => {
    const { fetchFn, c } = mockWith()
    const started = await runSample(API, 'sample-02', DEVICE, fetchFn)
    expect(started).toMatchObject({ reportId: expect.stringMatching(REPORT_ID) })
    const { reportId } = started as { reportId: string }
    const result = await pollReport(API, reportId, { fetchFn, sleep: c.sleep, now: c.now })
    expect(result).toMatchObject({ status: 'done', mode: 'sample', published: false, level: 'knee' })
    expect((await getPins(API, fetchFn)).some((pin) => pin.id === reportId)).toBe(false)
  })

  it('a sample the list doesn\'t hold is a 404 not_found', async () => {
    const notFound = { status: 404, code: 'not_found' }
    await expect(runSample(API, 'sample-99', DEVICE, mockWith().fetchFn)).rejects.toMatchObject(notFound)
    // samples_one lists only the first.
    await expect(runSample(API, 'sample-02', DEVICE, mockWith('samples_one').fetchFn)).rejects.toMatchObject(notFound)
  })
})

describe('the map', () => {
  const ageOf = (pin: { capturedAt: string }, at = NOW) => at - Date.parse(pin.capturedAt)

  it('serves a fresh live pin, a faded one, one past 3 hours, a demo pin and one with an unknown level', async () => {
    const { fetchFn } = mockWith()
    type RawPin = { id: string; mode: string; level: string; capturedAt: string }
    const raw = ((await (await fetchFn(`${API}/map/pins`)).json()) as { pins: RawPin[] }).pins
    expect(raw).toHaveLength(6)
    expect(raw.filter((pin) => pin.level === 'ankle_deep')).toHaveLength(1)

    // Task 5 drops the one it can't word.
    const pins = await getPins(API, fetchFn)
    expect(pins).toHaveLength(5)
    expect(pins.every((pin) => pin.id.match(REPORT_ID))).toBe(true)

    const live = pins.filter((pin) => pin.mode === 'live')
    expect(live).toHaveLength(4)
    const fresh = live.filter((pin) => ageOf(pin) < 3_600_000)
    const faded = live.filter((pin) => ageOf(pin) >= 3_600_000 && ageOf(pin) < 10_800_000)
    const gone = live.filter((pin) => ageOf(pin) >= 10_800_000)
    expect([fresh.length, faded.length, gone.length]).toEqual([2, 1, 1])

    const demo = pins.filter((pin) => pin.mode === 'demo')
    expect(demo).toHaveLength(1)
    expect(demo[0]).toMatchObject({ gpsAccuracyM: null, place: 'Marikina', event: 'Typhoon Ondoy' })
    expect(demo[0].credit).toMatch(/CC BY/)
    expect(ageOf(demo[0])).toBeGreaterThan(10_800_000)
    for (const pin of live) expect(pin.credit).toBeUndefined()
  })

  it('keeps two fresh live pins within 300 m of each other, for the nearby count', async () => {
    const pins = (await getPins(API, mockWith().fetchFn)).filter((pin) => pin.mode === 'live' && ageOf(pin) < 3_600_000)
    const [a, b] = pins
    const metres = Math.hypot((a.lat - b.lat) * 111_000, (a.lng - b.lng) * 107_000)
    expect(metres).toBeGreaterThan(0)
    expect(metres).toBeLessThan(300)
  })

  it('ages with the clock it is given: pin times are fixed when the mock is made, so a fresh pin fades', async () => {
    const { fetchFn, c } = mockWith()
    const before = await getPins(API, fetchFn)
    c.advance(2 * 3_600_000)
    const after = await getPins(API, fetchFn)
    expect(after.map((pin) => pin.capturedAt)).toEqual(before.map((pin) => pin.capturedAt))
    const fresh = after.filter((pin) => pin.mode === 'live' && ageOf(pin, c.now()) < 3_600_000)
    expect(fresh).toHaveLength(0)
    expect(after.filter((pin) => pin.mode === 'live' && ageOf(pin, c.now()) < 10_800_000)).toHaveLength(2)
  })

  it('pins_none is an empty map', async () => {
    expect(await getPins(API, mockWith('pins_none').fetchFn)).toEqual([])
  })

  it('shows the person\'s own live pin once the result is in, at 4 decimals, and counts its flags', async () => {
    const { fetchFn, reportId } = await takePhoto('level_knee', { ...REQ, lat: 14.60951234, lng: 120.98941234 })
    const own = (await getPins(API, fetchFn)).find((pin) => pin.id === reportId)
    expect(own).toMatchObject({
      lat: 14.6095,
      lng: 120.9894,
      mode: 'live',
      level: 'knee',
      passability: 'NPLV',
      gpsAccuracyM: 12,
      flags: 0,
      depthInMin: 15,
      depthInMax: 18,
    })
    expect(await flagPin(API, reportId, OTHER_DEVICE, fetchFn)).toEqual({ flags: 1 })
    expect((await getPins(API, fetchFn)).find((pin) => pin.id === reportId)?.flags).toBe(1)
  })

  it('answers a flag with the count, once a phone: a repeat leaves it unchanged', async () => {
    const { fetchFn } = mockWith()
    const [pin] = (await getPins(API, fetchFn)).filter((p) => p.mode === 'live')
    expect(pin.flags).toBe(0)
    expect(await flagPin(API, pin.id, DEVICE, fetchFn)).toEqual({ flags: 1 })
    expect(await flagPin(API, pin.id, DEVICE, fetchFn)).toEqual({ flags: 1 })
    expect(await flagPin(API, pin.id, OTHER_DEVICE, fetchFn)).toEqual({ flags: 2 })
    expect((await getPins(API, fetchFn)).find((p) => p.id === pin.id)?.flags).toBe(2)
  })

  it('refuses a flag on a demo pin, a pin past 3 hours and an id it doesn\'t know with 404 not_found', async () => {
    const { fetchFn } = mockWith()
    const pins = await getPins(API, fetchFn)
    const demo = pins.find((pin) => pin.mode === 'demo')
    const gone = pins.find((pin) => pin.mode === 'live' && ageOf(pin) >= 10_800_000)
    for (const id of [demo?.id ?? '', gone?.id ?? '', `r_${'a'.repeat(32)}`]) {
      await expect(flagPin(API, id, DEVICE, fetchFn)).rejects.toMatchObject({ status: 404, code: 'not_found' })
    }
  })

  it('gives a pin detail from GET /reports/{id}: links while it is visible, a demo pin its credit', async () => {
    const { fetchFn } = mockWith()
    const pins = await getPins(API, fetchFn)
    const live = pins.find((pin) => pin.mode === 'live' && ageOf(pin) < 3_600_000) as (typeof pins)[number]
    const detail = await getReport(API, live.id, fetchFn)
    expect(detail).toMatchObject({
      reportId: live.id,
      status: 'done',
      mode: 'live',
      published: true,
      level: live.level,
      landmark: live.landmark,
      passability: live.passability,
      basis: live.basis,
      capturedAt: live.capturedAt,
    })
    expect(detail?.photoUrl).toMatch(/^data:image\//)
    expect(await getLayers(detail?.layersUrl ?? '', fetchFn)).toMatchObject({ version: 1 })

    const demo = pins.find((pin) => pin.mode === 'demo') as (typeof pins)[number]
    const demoDetail = await getReport(API, demo.id, fetchFn)
    expect(demoDetail).toMatchObject({ mode: 'demo', credit: demo.credit, place: demo.place, event: demo.event })
    expect(demoDetail?.photoUrl).toMatch(/^data:image\//)

    // Past 3 hours the pin is off the map, and the API issues no photo links for it.
    const gone = pins.find((pin) => pin.mode === 'live' && ageOf(pin) >= 10_800_000) as (typeof pins)[number]
    const goneDetail = await getReport(API, gone.id, fetchFn)
    expect(goneDetail).toMatchObject({ status: 'done', level: gone.level })
    expect(goneDetail?.photoUrl).toBeUndefined()
    expect(goneDetail?.layersUrl).toBeUndefined()
  })

  it('answers GET /reports with 404 for an id it never gave', async () => {
    expect(await getReport(API, `r_${'b'.repeat(32)}`, mockWith().fetchFn)).toBeUndefined()
  })
})

describe('the mock itself', () => {
  it('marks every answer with LUSOT_MOCK_API, errors and empty ones included', async () => {
    const { fetchFn } = mockWith()
    const answers = [
      await fetchFn(`${API}/map/pins`),
      await fetchFn(`${API}/samples`),
      await fetchFn(`${API}/nowhere`),
      await fetchFn(`${API}/reports/r_${'c'.repeat(32)}`),
      await createMockFetch({ scenario: 'uploads_paused' })(`${API}/uploads`, { method: 'POST', body: '{}' }),
    ]
    expect(answers.map((res) => res.status)).toEqual([200, 200, 404, 404, 503])
    for (const res of answers) expect(res.headers.get('x-lusot-mock')).toBe(MOCK_MARKER)
    expect(MOCK_MARKER).toBe('LUSOT_MOCK_API')
  })

  it('never touches the network, whatever it is asked for', async () => {
    const network = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('no network request is allowed here'))
    await takePhoto()
    await takePhoto('failed_model_calls_paused')
    await getPins(API, createMockFetch())
    expect(network).not.toHaveBeenCalled()
  })

  it('draws every image it links, and none of them is a stored file', async () => {
    const { result, fetchFn } = await takePhoto()
    const samples = await getSamples(API, fetchFn)
    for (const url of [result.photoUrl, result.overlayUrl, ...samples.map((sample) => sample.photoUrl)]) {
      expect(url).toMatch(/^data:image\/[a-z]+;base64,/)
    }
  })

  it('rejects with an AbortError when the request was already stopped', async () => {
    const stopped = AbortSignal.abort()
    await expect(createMockFetch()(`${API}/samples`, { signal: stopped })).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('gives each mock its own reports, so one test never sees another\'s', async () => {
    const first = mockWith()
    const { reportId } = await requestUpload(API, REQ, DEVICE, first.fetchFn)
    expect(await getReport(API, reportId, first.fetchFn)).toBeDefined()
    expect(await getReport(API, reportId, mockWith().fetchFn)).toBeUndefined()
  })

  it('names an unknown scenario and lists the ones it has', () => {
    expect(() => createMockFetch({ scenario: 'level_ankle' as Scenario })).toThrow(/level_ankle.*level_knee/s)
  })
})

describe('choosing a scenario', () => {
  it('lists every scenario once, the default first', () => {
    const names = scenarioNames()
    expect(names[0]).toBe('level_knee')
    expect(new Set(names).size).toBe(names.length)
    for (const name of [
      'level_landmark', 'level_floor', 'level_below_gutter', 'level_above_chest', 'level_private', 'no_flood_seen',
      'pending_forever', 'uploads_paused', 'device_limit', 'global_cap', 'throttled', 'samples_none', 'samples_one',
      'samples_two', 'pins_none',
      ...REFUSED_REASONS.map((reason) => `refused_${reason}`),
      ...FAILED_REASONS.map((reason) => `failed_${reason}`),
    ]) {
      expect(names, name).toContain(name)
    }
  })

  it('takes the query flag first, then VITE_API_MOCK_SCENARIO, then level_knee', () => {
    expect(pickScenario('?mock=refused_too_dark', 'no_flood_seen')).toBe('refused_too_dark')
    expect(pickScenario('?a=1&mock=samples_none&b=2', undefined)).toBe('samples_none')
    expect(pickScenario('', 'no_flood_seen')).toBe('no_flood_seen')
    expect(pickScenario('?other=1', 'no_flood_seen')).toBe('no_flood_seen')
    expect(pickScenario('', undefined)).toBe('level_knee')
    expect(pickScenario('', '')).toBe('level_knee')
  })

  it('fails loudly on a name it doesn\'t know, from the flag or the variable', () => {
    expect(() => pickScenario('?mock=nope', undefined)).toThrow(/nope/)
    expect(() => pickScenario('', 'nope')).toThrow(/nope/)
  })

  it.each(scenarioNames())('%s makes a working mock', async (scenario) => {
    const { fetchFn } = mockWith(scenario)
    expect((await fetchFn(`${API}/samples`)).status).toBe(200)
    expect((await fetchFn(`${API}/map/pins`)).status).toBe(200)
  })
})
