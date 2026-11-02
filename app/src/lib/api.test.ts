import { afterEach, expect, it, vi } from 'vitest'
import {
  apiBaseUrl,
  ask,
  type AskAnswer,
  askVoice,
  flagPin,
  getLayers,
  getPins,
  getReport,
  getSamples,
  HttpError,
  MalformedAnswerError,
  type OverlayData,
  type OverlayRef,
  postToS3,
  RequestTimeoutError,
  type Reading,
  requestTry,
  requestUpload,
  runSample,
} from './api'

const API = 'https://api.example.test'
const ID = 'r_0123456789abcdef0123456789abcdef'
const DEVICE = '0f8e4a52-3c1d-4b7a-9e26-5d0c8b1f7a43'
const REQ = {
  lat: 14.6095,
  lng: 120.9894,
  gpsAccuracyM: 12,
  capturedAt: '2026-10-30T10:05:12.000Z',
  nudgeM: 18,
  consentVersion: '3f9a1c07',
}
const UPLOAD = {
  url: 'https://lusot-test01-uploads.s3.ap-southeast-1.amazonaws.com/',
  fields: { 'Content-Type': 'image/jpeg', key: `raw/${ID}.jpg`, Policy: 'cG9saWN5', 'X-Amz-Signature': 'c2lnbmF0dXJl' },
}
const LAYERS_URL = 'https://lusot-test01-uploads.s3.ap-southeast-1.amazonaws.com/overlay/layers.json?X-Amz-Signature=c2ln'

afterEach(() => {
  vi.useRealTimers()
})

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', ...headers } })
}

// A fetch that answers each call with the next response.
function fetchReplying(...responses: Response[]) {
  const fetchFn = vi.fn<typeof fetch>()
  for (const response of responses) fetchFn.mockResolvedValueOnce(response)
  return fetchFn
}

// The headers of the fetch's call at this index.
function headersOf(fetchFn: ReturnType<typeof fetchReplying>, call = 0): Headers {
  return new Headers(fetchFn.mock.calls[call][1]?.headers)
}

// Follows a promise without awaiting it, so a test can check whether it has settled yet.
function track(promise: Promise<unknown>) {
  const state: { settled: boolean; error?: unknown } = { settled: false }
  promise.then(
    () => {
      state.settled = true
    },
    (error: unknown) => {
      state.settled = true
      state.error = error
    },
  )
  return state
}

// A level result as GET /reports/{id} returns it (MS4's §4.3), with one dropped reference.
const LEVEL_REPORT = {
  reportId: ID,
  status: 'done',
  capturedAt: '2026-10-30T10:05:12Z',
  mode: 'live',
  published: true,
  noFloodSeen: false,
  level: 'knee',
  landmark: 'rim_three_quarters',
  passability: 'NPLV',
  basis: { vehicles: 1, people: 1 },
  levelIsFloor: false,
  levelFrom: 'landmark',
  readings: [
    { id: 1, kind: 'wheel', landmark: 'rim_three_quarters', level: 'knee', used: true, dropped: null },
    { id: 2, kind: 'person', landmark: null, level: null, used: false, dropped: 'occluded' },
  ],
  gpsAccuracyM: 12,
  photoUrl: 'https://bucket.example.test/blurred/photo.jpg?sig=1',
  overlayUrl: 'https://bucket.example.test/overlay/photo.jpg?sig=2',
  layersUrl: 'https://bucket.example.test/overlay/photo.json?sig=3',
}

const LIVE_PIN = {
  id: ID,
  lat: 14.6095,
  lng: 120.9894,
  gpsAccuracyM: 12,
  capturedAt: '2026-10-30T10:05:12Z',
  mode: 'live',
  level: 'knee',
  landmark: 'rim_three_quarters',
  passability: 'NPLV',
  levelIsFloor: false,
  basis: { vehicles: 1, people: 0 },
  flags: 0,
}
const DEMO_PIN = {
  ...LIVE_PIN,
  id: 'r_fedcba9876543210fedcba9876543210',
  lat: 14.5547,
  lng: 121.0244,
  gpsAccuracyM: null,
  mode: 'demo',
  credit: 'Photo: A. Contributor, CC BY 4.0, faces and plates blurred by Lusot',
  place: 'Ayala Avenue, Makati',
  event: 'Typhoon Example, 2025',
}

// C524's layers file: the water outline and two references, the second dropped.
const LAYERS = {
  version: 1,
  width: 1600,
  height: 1200,
  water: [
    [
      [0, 700],
      [1600, 690],
      [1600, 1200],
      [0, 1200],
    ],
  ],
  refs: [
    {
      id: 1,
      kind: 'wheel',
      box: [400, 600, 700, 900],
      outline: [
        [
          [400, 600],
          [700, 600],
          [700, 900],
        ],
      ],
      landmark: 'rim_three_quarters',
      level: 'knee',
      level_from: 'landmark',
      used: true,
      dropped: null,
      rechecked: false,
      rim_outline: null,
      rim: null,
      waterline: [
        [400, 705],
        [700, 702],
      ],
    },
    {
      id: 2,
      kind: 'person',
      box: [900, 300, 1100, 1000],
      outline: [],
      landmark: null,
      level: null,
      level_from: null,
      used: false,
      dropped: 'occluded',
      rechecked: false,
      rim_outline: null,
      rim: null,
      waterline: null,
    },
  ],
}

it('apiBaseUrl drops trailing slashes and is empty when VITE_API_URL is unset', () => {
  expect(apiBaseUrl('https://api.example.test')).toBe('https://api.example.test')
  expect(apiBaseUrl('https://api.example.test//')).toBe('https://api.example.test')
  expect(apiBaseUrl('')).toBe('')
  expect(apiBaseUrl(undefined)).toBe('')
})

it('requestUpload sends the device header and a body with nudgeM and consentVersion', async () => {
  const fetchFn = fetchReplying(json(201, { reportId: ID, upload: UPLOAD, expiresInS: 300 }))

  const result = await requestUpload(API, REQ, DEVICE, fetchFn)

  expect(result).toEqual({ reportId: ID, upload: UPLOAD })
  expect(fetchFn).toHaveBeenCalledOnce()
  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(`${API}/uploads`)
  expect(init?.method).toBe('POST')
  expect(headersOf(fetchFn).get('content-type')).toBe('application/json')
  expect(headersOf(fetchFn).get('x-lusot-device')).toBe(DEVICE)
  expect(JSON.parse(String(init?.body))).toEqual(REQ)
})

it('requestUpload sends only the request fields', async () => {
  const fetchFn = fetchReplying(json(201, { reportId: ID, upload: UPLOAD, expiresInS: 300 }))
  // A caller's object can hold more than the type names; only the request's fields leave the phone.
  const withExtra = { ...REQ, deviceId: DEVICE, photo: 'jpeg bytes' }

  await requestUpload(API, withExtra, DEVICE, fetchFn)

  expect(Object.keys(JSON.parse(String(fetchFn.mock.calls[0][1]?.body))).sort()).toEqual(Object.keys(REQ).sort())
})

it.each([
  ['a null body', null],
  ['no upload', { reportId: ID, expiresInS: 300 }],
  ['a report id that is not text', { reportId: 42, upload: UPLOAD }],
  ['an upload without a url', { reportId: ID, upload: { fields: UPLOAD.fields } }],
  ['upload fields that are not text', { reportId: ID, upload: { url: UPLOAD.url, fields: { key: 7 } } }],
  ['upload fields as a list', { reportId: ID, upload: { url: UPLOAD.url, fields: ['key'] } }],
])('requestUpload throws MalformedAnswerError on a 201 with %s', async (_, body) => {
  // A named error, not a TypeError, so retryOnce never reads it as a network error and posts again.
  const upload = requestUpload(API, REQ, DEVICE, fetchReplying(json(201, body)))

  await expect(upload).rejects.toBeInstanceOf(MalformedAnswerError)
  await expect(upload).rejects.toMatchObject({ name: 'MalformedAnswerError' })
})

it('postToS3 appends every field before the file', async () => {
  const fetchFn = fetchReplying(new Response(null, { status: 204 }))
  const jpeg = new Blob(['jpeg bytes'], { type: 'image/jpeg' })

  await postToS3(UPLOAD, jpeg, fetchFn)

  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(UPLOAD.url)
  expect(init?.method).toBe('POST')
  const form = init?.body as FormData
  // S3 ignores any field that comes after the file.
  expect([...form.keys()]).toEqual([...Object.keys(UPLOAD.fields), 'file'])
  for (const [name, value] of Object.entries(UPLOAD.fields)) expect(form.get(name)).toBe(value)
  const file = form.get('file') as Blob
  expect(file.size).toBe(jpeg.size)
  expect(file.type).toBe('image/jpeg')
})

it('getReport gives the result fields and nothing else', async () => {
  // Anything outside the result, such as a location, stays out of the app's state.
  const fetchFn = fetchReplying(json(200, { ...LEVEL_REPORT, lat: 14.6095, lng: 120.9894, nudgeM: 18 }))

  const result = await getReport(API, ID, fetchFn)

  expect(result).toEqual(LEVEL_REPORT)
  expect(fetchFn.mock.calls[0][0]).toBe(`${API}/reports/${ID}`)
})

it("getReport gives a demo pin's credit, place and event", async () => {
  const demo = { ...LEVEL_REPORT, mode: 'demo', credit: DEMO_PIN.credit, place: DEMO_PIN.place, event: DEMO_PIN.event }

  expect(await getReport(API, ID, fetchReplying(json(200, demo)))).toEqual(demo)
})

it('getReport reads a missing published as false', async () => {
  const pending = { reportId: ID, status: 'pending', capturedAt: '2026-10-30T10:05:12Z', mode: 'private' }

  expect(await getReport(API, ID, fetchReplying(json(200, pending)))).toEqual({ ...pending, published: false })
})

it('getReport gives undefined on a 404', async () => {
  // A fresh report the index hasn't caught up with, or one past expiresAt (C526).
  expect(await getReport(API, ID, fetchReplying(json(404, { error: 'not_found' })))).toBeUndefined()
})

it('requests give up on a stalled connection with RequestTimeoutError', async () => {
  vi.useFakeTimers()
  const stalled = vi.fn<typeof fetch>(() => new Promise<Response>(() => {}))
  const jpeg = new Blob(['jpeg bytes'], { type: 'image/jpeg' })

  const upload = track(requestUpload(API, REQ, DEVICE, stalled))
  const report = track(getReport(API, ID, stalled))
  const s3 = track(postToS3(UPLOAD, jpeg, stalled))

  await vi.advanceTimersByTimeAsync(14_999)
  expect([upload.settled, report.settled, s3.settled]).toEqual([false, false, false])
  await vi.advanceTimersByTimeAsync(1)
  expect(upload.error).toBeInstanceOf(RequestTimeoutError)
  expect(report.error).toBeInstanceOf(RequestTimeoutError)
  expect(upload.error).toMatchObject({ name: 'RequestTimeoutError', message: 'No answer after 15 s' })
  // The photo upload gets longer.
  expect(s3.settled).toBe(false)
  await vi.advanceTimersByTimeAsync(45_000)
  expect(s3.error).toBeInstanceOf(RequestTimeoutError)
  expect(s3.error).toMatchObject({ message: 'No answer after 60 s' })
  // Each stalled request is aborted too, which frees the connection.
  expect(stalled.mock.calls.map(([, init]) => init?.signal?.aborted)).toEqual([true, true, true])
})

it('non-2xx responses throw with the status', async () => {
  const refused = requestUpload(API, REQ, DEVICE, fetchReplying(json(422, { error: 'capture_too_old' })))
  await expect(refused).rejects.toThrow('HTTP 422 capture_too_old')
  await expect(refused).rejects.toBeInstanceOf(HttpError)
  await expect(refused).rejects.toMatchObject({ status: 422, code: 'capture_too_old', isDeviceLimit: false })

  // S3 answers in XML, so only the status is named.
  const denied = new Response('<Error><Code>AccessDenied</Code></Error>', { status: 403 })
  const jpeg = new Blob(['jpeg bytes'], { type: 'image/jpeg' })
  await expect(postToS3(UPLOAD, jpeg, fetchReplying(denied))).rejects.toThrow('HTTP 403')

  const broken = fetchReplying(json(500, { error: 'internal' }))
  await expect(getReport(API, ID, broken)).rejects.toThrow('HTTP 500 internal')
})

it("a 400 names the API's detail", async () => {
  const detail = 'lat must be a number from -90 to 90'
  const invalid = requestUpload(API, REQ, DEVICE, fetchReplying(json(400, { error: 'bad_request', detail })))

  await expect(invalid).rejects.toThrow(`HTTP 400 bad_request: ${detail}`)
  await expect(invalid).rejects.toMatchObject({ status: 400, code: 'bad_request', detail })
})

it.each(['device_limit', 'global_cap', 'question_limit', 'question_cap'])(
  'a 429 %s is a device limit, with its Retry-After',
  async (code) => {
    const limited = requestUpload(API, REQ, DEVICE, fetchReplying(json(429, { error: code }, { 'retry-after': '1234' })))

    await expect(limited).rejects.toMatchObject({ status: 429, code, isDeviceLimit: true, retryAfterMs: 1_234_000 })
  },
)

it("API Gateway's throttling 429 isn't a device limit", async () => {
  // API Gateway's own throttle answers with a message and no error code (MS4's C522).
  const throttled = requestUpload(API, REQ, DEVICE, fetchReplying(json(429, { message: 'Too Many Requests' })))

  await expect(throttled).rejects.toMatchObject({ status: 429, code: undefined, isDeviceLimit: false, retryAfterMs: undefined })
})

it('only a 429 makes a limit code a device limit', () => {
  expect(new HttpError(503, 'device_limit').isDeviceLimit).toBe(false)
  expect(new HttpError(429, 'device_limit').isDeviceLimit).toBe(true)
})

it('Retry-After is read only as whole seconds', async () => {
  const at = (value: string) => requestUpload(API, REQ, DEVICE, fetchReplying(json(429, {}, { 'retry-after': value })))

  await expect(at('7')).rejects.toMatchObject({ retryAfterMs: 7000 })
  await expect(at(' 7 ')).rejects.toMatchObject({ retryAfterMs: 7000 })
  // An HTTP date, a negative or a fraction isn't read; the poll then waits its interval plus jitter.
  await expect(at('Fri, 30 Oct 2026 11:00:00 GMT')).rejects.toMatchObject({ retryAfterMs: undefined })
  await expect(at('-5')).rejects.toMatchObject({ retryAfterMs: undefined })
  await expect(at('1.5')).rejects.toMatchObject({ retryAfterMs: undefined })
})

it('getPins reads the map route', async () => {
  const noId = { ...LIVE_PIN, id: undefined }
  const demoNoCredit = { ...DEMO_PIN, id: `r_${'b'.repeat(32)}`, credit: undefined }
  const demoBlankCredit = { ...DEMO_PIN, id: `r_${'c'.repeat(32)}`, credit: '  ' }
  const fetchFn = fetchReplying(json(200, { pins: [LIVE_PIN, noId, DEMO_PIN, demoNoCredit, demoBlankCredit] }))

  const pins = await getPins(API, fetchFn)

  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(`${API}/map/pins`)
  expect(init?.method ?? 'GET').toBe('GET')
  expect(pins.map((pin) => [pin.id, pin.lat, pin.lng])).toEqual([
    [LIVE_PIN.id, LIVE_PIN.lat, LIVE_PIN.lng],
    [DEMO_PIN.id, DEMO_PIN.lat, DEMO_PIN.lng],
  ])
  expect(pins).toEqual([LIVE_PIN, DEMO_PIN])
})

it('getPins skips a pin with no usable position', async () => {
  const noLat = { ...LIVE_PIN, id: `r_${'d'.repeat(32)}`, lat: undefined }
  const textLng = { ...LIVE_PIN, id: `r_${'e'.repeat(32)}`, lng: '120.9894' }

  expect(await getPins(API, fetchReplying(json(200, { pins: [noLat, textLng, LIVE_PIN] })))).toEqual([LIVE_PIN])
})

it('getPins skips a pin whose level or class is not one of the known ones', async () => {
  // One such pin would otherwise break the wording of every viewer's map list.
  const unknownLevel = { ...LIVE_PIN, id: `r_${'f'.repeat(32)}`, level: 'ankle_deep' }
  const unknownClass = { ...LIVE_PIN, id: `r_${'a'.repeat(32)}`, passability: 'PASSABLE' }
  const noLevel = { ...DEMO_PIN, level: undefined }

  expect(await getPins(API, fetchReplying(json(200, { pins: [unknownLevel, unknownClass, noLevel, LIVE_PIN] })))).toEqual([
    LIVE_PIN,
  ])
})

it('getPins throws on an error or an answer without a pins list', async () => {
  await expect(getPins(API, fetchReplying(json(503, { message: 'Service Unavailable' })))).rejects.toBeInstanceOf(HttpError)
  await expect(getPins(API, fetchReplying(json(200, { features: [] })))).rejects.toThrow()
})

it('getSamples keeps only credited samples under an allowed licence', async () => {
  const sample = (sampleId: string, license: string, credit?: string | null) => ({
    sampleId,
    // null leaves the credit out, as JSON drops an undefined field.
    credit: credit === null ? undefined : (credit ?? `Photo: ${sampleId}`),
    license,
    place: 'España Boulevard, Manila',
    date: '2025-07-24',
    photoUrl: `https://bucket.example.test/samples/${sampleId}.jpg?sig=1`,
  })
  const samples = [
    sample('cc0', 'CC0'),
    sample('cc0-v1', 'CC0 1.0'),
    sample('ccby2', 'CC BY 2.0'),
    sample('ccby4', 'CC BY 4.0'),
    sample('consented', 'used with permission'),
    sample('bysa', 'CC BY-SA 4.0'),
    sample('attribution-sa', 'Attribution-ShareAlike 4.0'),
    sample('bync', 'CC BY-NC 2.0'),
    sample('pd', 'Public domain'),
    sample('pd-lower', 'public domain'),
    sample('m9-v3', 'Used with permission (M9-v3)'),
    sample('uncredited', 'CC0', null),
    sample('blank-credit', 'CC BY 4.0', ' '),
  ]
  const fetchFn = fetchReplying(json(200, { samples }))

  const kept = await getSamples(API, fetchFn)

  expect(fetchFn.mock.calls[0][0]).toBe(`${API}/samples`)
  // Public domain by its exact value (Rene's OK, Nov 2: Wikimedia Commons' own public-domain photos).
  expect(kept.map((s) => s.sampleId)).toEqual(['cc0', 'cc0-v1', 'ccby2', 'ccby4', 'consented', 'pd'])
  expect(kept[0]).toEqual(samples[0])
})

it('runSample gives the report id on a 201, and sends the device header', async () => {
  const fetchFn = fetchReplying(json(201, { reportId: ID }))

  expect(await runSample(API, 'manila-espana-01', DEVICE, fetchFn)).toEqual({ reportId: ID })
  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(`${API}/samples/manila-espana-01`)
  expect(init?.method).toBe('POST')
  expect(headersOf(fetchFn).get('x-lusot-device')).toBe(DEVICE)
})

it('runSample gives the saved answer on a 200 with saved: true', async () => {
  // MS4's C527 while model calls are paused: the seeding run's result, marked as saved and dated.
  const saved = {
    saved: true,
    savedAt: '2026-10-30',
    result: { status: 'done', noFloodSeen: false, level: 'half_knee', landmark: 'mid_shin', passability: 'PATV', levelIsFloor: false },
  }

  expect(await runSample(API, 'manila-espana-01', DEVICE, fetchReplying(json(200, saved)))).toEqual(saved)

  const refused = { saved: true, savedAt: '2026-10-30', result: { status: 'refused', refusalReason: 'water_unsure' } }
  expect(await runSample(API, 'manila-espana-01', DEVICE, fetchReplying(json(200, refused)))).toEqual(refused)
})

it('runSample throws HttpError on a 503 uploads_paused and a 404 not_found', async () => {
  const paused = runSample(API, 'manila-espana-01', DEVICE, fetchReplying(json(503, { error: 'uploads_paused' })))
  await expect(paused).rejects.toBeInstanceOf(HttpError)
  await expect(paused).rejects.toMatchObject({ status: 503, code: 'uploads_paused' })

  const gone = runSample(API, 'manila-espana-01', DEVICE, fetchReplying(json(404, { error: 'not_found' })))
  await expect(gone).rejects.toMatchObject({ status: 404, code: 'not_found' })
})

it('runSample throws on a 201 without a report id', async () => {
  // Polling "undefined" for 10 minutes would only end on "No result yet".
  await expect(runSample(API, 'manila-espana-01', DEVICE, fetchReplying(json(201, {})))).rejects.toThrow()
})

it('requestTry sends only consentVersion with the device header and returns the link', async () => {
  const fetchFn = fetchReplying(json(201, { reportId: ID, upload: UPLOAD, expiresInS: 300 }))

  const result = await requestTry(API, '0a1b2c3d', DEVICE, fetchFn)

  expect(result).toEqual({ reportId: ID, upload: UPLOAD })
  expect(fetchFn).toHaveBeenCalledOnce()
  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(`${API}/try`)
  expect(init?.method).toBe('POST')
  expect(headersOf(fetchFn).get('content-type')).toBe('application/json')
  expect(headersOf(fetchFn).get('x-lusot-device')).toBe(DEVICE)
  expect(init?.body).toBe('{"consentVersion":"0a1b2c3d"}')
})

it.each([
  [503, 'model_calls_paused', false],
  [429, 'daily_cap', true],
])("requestTry throws HttpError with the API's code: %i %s", async (status, code, isDeviceLimit) => {
  const refused = requestTry(API, '0a1b2c3d', DEVICE, fetchReplying(json(status, { error: code })))

  await expect(refused).rejects.toBeInstanceOf(HttpError)
  await expect(refused).rejects.toMatchObject({ status, code, isDeviceLimit })
})

it.each([
  ['a null body', null],
  ['no upload', { reportId: ID, expiresInS: 300 }],
  ['a report id that is not text', { reportId: 42, upload: UPLOAD }],
  ['an upload without a url', { reportId: ID, upload: { fields: UPLOAD.fields } }],
])('requestTry throws MalformedAnswerError on a 201 with %s', async (_, body) => {
  const attempt = requestTry(API, '0a1b2c3d', DEVICE, fetchReplying(json(201, body)))

  await expect(attempt).rejects.toBeInstanceOf(MalformedAnswerError)
  await expect(attempt).rejects.toMatchObject({ name: 'MalformedAnswerError' })
})

it('flagPin posts to the pin and gives its count, a repeat included', async () => {
  const fetchFn = fetchReplying(json(200, { flags: 3 }), json(200, { flags: 3 }))

  expect(await flagPin(API, ID, DEVICE, fetchFn)).toEqual({ flags: 3 })
  // A repeat from the same phone answers 200 with the count unchanged (MS4's C522).
  expect(await flagPin(API, ID, DEVICE, fetchFn)).toEqual({ flags: 3 })
  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(`${API}/reports/${ID}/flag`)
  expect(init?.method).toBe('POST')
  expect(headersOf(fetchFn).get('x-lusot-device')).toBe(DEVICE)
})

it('flagPin throws HttpError on a 404', async () => {
  // A demo pin, or a pin that has left the map.
  const missing = flagPin(API, ID, DEVICE, fetchReplying(json(404, { error: 'not_found' })))

  await expect(missing).rejects.toBeInstanceOf(HttpError)
  await expect(missing).rejects.toMatchObject({ status: 404, code: 'not_found' })
})

it('the device header goes only with uploads, samples and flags', async () => {
  const fetchFn = fetchReplying(
    json(200, LEVEL_REPORT),
    json(200, { pins: [] }),
    json(200, { samples: [] }),
    json(200, LAYERS),
    new Response(null, { status: 204 }),
  )

  await getReport(API, ID, fetchFn)
  await getPins(API, fetchFn)
  await getSamples(API, fetchFn)
  await getLayers(LAYERS_URL, fetchFn)
  await postToS3(UPLOAD, new Blob(['jpeg bytes'], { type: 'image/jpeg' }), fetchFn)

  expect(fetchFn).toHaveBeenCalledTimes(5)
  for (let call = 0; call < 5; call++) expect(headersOf(fetchFn, call).has('x-lusot-device')).toBe(false)
})

it('getLayers gives the layers file in C524 shape', async () => {
  const fetchFn = fetchReplying(json(200, LAYERS))

  expect(await getLayers(LAYERS_URL, fetchFn)).toEqual(LAYERS)
  expect(fetchFn.mock.calls[0][0]).toBe(LAYERS_URL)
})

// MS4's floor keys (C54): each reference in the layers file carries level_is_floor (true, false, or null where it has
// no level) and each reading carries levelIsFloor. An answer from before MS4 rolled out has neither key.
it("getLayers keeps each reference's level_is_floor as the file has it: true, false, null, and absent", async () => {
  const [wheel, person] = LAYERS.refs
  const floors: Pick<OverlayRef, 'level_is_floor'>[] = [{ level_is_floor: true }, { level_is_floor: false }, { level_is_floor: null }]
  const file = { ...LAYERS, refs: [{ ...wheel, ...floors[0] }, { ...person, ...floors[1] }, { ...wheel, id: 3, ...floors[2] }, { ...wheel, id: 4 }] }

  const layers = (await getLayers(LAYERS_URL, fetchReplying(json(200, file)))) as OverlayData

  expect(layers.refs.map((ref) => ref.level_is_floor)).toEqual([true, false, null, undefined])
  expect('level_is_floor' in layers.refs[3]).toBe(false)
})

it('getReport keeps levelIsFloor on each reading: true, false, null, and absent', async () => {
  const floors: Pick<Reading, 'levelIsFloor'>[] = [{ levelIsFloor: true }, { levelIsFloor: false }, { levelIsFloor: null }]
  const [wheel, person] = LEVEL_REPORT.readings
  const readings = [{ ...wheel, ...floors[0] }, { ...person, ...floors[1] }, { ...wheel, id: 3, ...floors[2] }, { ...wheel, id: 4 }]

  const report = await getReport(API, ID, fetchReplying(json(200, { ...LEVEL_REPORT, readings })))

  expect(report?.readings?.map((reading) => reading.levelIsFloor)).toEqual([true, false, null, undefined])
  expect(report?.readings?.[3] && 'levelIsFloor' in report.readings[3]).toBe(false)
})

it('getLayers gives undefined when the fetch fails or the JSON does not parse', async () => {
  // A bucket without GET in its CORS rule fails as a network error in the browser (N14).
  const blocked = vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError('Failed to fetch'))
  expect(await getLayers(LAYERS_URL, blocked)).toBeUndefined()

  const garbled = new Response('{"version": 1, "water": [', { status: 200, headers: { 'content-type': 'application/json' } })
  expect(await getLayers(LAYERS_URL, fetchReplying(garbled))).toBeUndefined()
})

it('getLayers gives undefined on an expired link or a file in another shape', async () => {
  const expired = new Response('<Error><Code>AccessDenied</Code></Error>', { status: 403 })
  expect(await getLayers(LAYERS_URL, fetchReplying(expired))).toBeUndefined()

  expect(await getLayers(LAYERS_URL, fetchReplying(json(200, { ...LAYERS, version: 2 })))).toBeUndefined()
  expect(await getLayers(LAYERS_URL, fetchReplying(json(200, { ...LAYERS, refs: undefined })))).toBeUndefined()
  expect(await getLayers(LAYERS_URL, fetchReplying(json(200, null)))).toBeUndefined()
})

it('getLayers gives undefined on a stalled link', async () => {
  vi.useFakeTimers()
  const layers = track(getLayers(LAYERS_URL, vi.fn<typeof fetch>(() => new Promise<Response>(() => {}))))

  await vi.advanceTimersByTimeAsync(15_000)

  expect(layers).toEqual({ settled: true })
})

// ---- Ask Lusot (its spec §4.8, §5) ----

const ASK_PIN = {
  id: ID,
  lat: 14.6095,
  lng: 120.9894,
  capturedAt: '2026-10-30T10:05:12Z',
  mode: 'live',
  flags: 0,
  gpsAccuracyM: 12,
  level: 'knee',
  landmark: 'rim_three_quarters',
  passability: 'NPLV',
  levelIsFloor: false,
  basis: { vehicles: 1, people: 0 },
  distanceM: 120,
}
const ASK_DEMO = {
  ...ASK_PIN,
  id: 'r_fedcba9876543210fedcba9876543210',
  mode: 'demo',
  capturedAt: '2009-09-26T01:30:00Z',
  gpsAccuracyM: null,
  level: 'above_chest',
  passability: 'NPATV',
  credit: 'Photo: Example Contributor (mock), CC BY 4.0',
  place: 'Marikina',
  event: 'Typhoon Ondoy',
  distanceM: 210,
}
const ANSWER: AskAnswer = {
  source: 'model',
  fallback: null,
  kind: 'reports',
  crossing: false,
  vehicle: 'light',
  place: { name: 'España Blvd cor. Maceda St', source: 'spots' },
  windowMin: 180,
  radiusM: 300,
  count: 1,
  reports: [ASK_PIN],
  demo: [ASK_DEMO],
  deepestId: ID,
  cited: [ID],
  suggestions: [],
} as AskAnswer
const HERE = { lat: 14.6095, lng: 120.9894, accuracyM: 20 }
const WAV = Uint8Array.from([0x52, 0x49, 0x46, 0x46, 0x00, 0xff, 0x10, 0x80])

it('ask posts the question and here with the device id, and gives the answer', async () => {
  const fetchFn = fetchReplying(json(200, { answer: ANSWER }))

  const { answer } = await ask(API, { question: 'Baha ba sa España cor. Maceda?', here: HERE }, DEVICE, fetchFn)

  expect(answer).toEqual(ANSWER)
  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(`${API}/ask`)
  expect(init?.method).toBe('POST')
  expect(headersOf(fetchFn).get('X-Lusot-Device')).toBe(DEVICE)
  expect(headersOf(fetchFn).get('content-type')).toBe('application/json')
  expect(JSON.parse(String(init?.body))).toEqual({ question: 'Baha ba sa España cor. Maceda?', here: HERE })
  // Only here's three fields are sent.
  const richer = fetchReplying(json(200, { answer: ANSWER }))
  await ask(API, { question: 'Baha?', here: { ...HERE, at: 1_700_000_000_000 } as typeof HERE }, DEVICE, richer)
  expect(JSON.parse(String(richer.mock.calls[0][1]?.body)).here).toEqual(HERE)
  // Without a location, no here is sent.
  const bare = fetchReplying(json(200, { answer: ANSWER }))
  await ask(API, { question: 'May baha ba?' }, DEVICE, bare)
  expect(JSON.parse(String(bare.mock.calls[0][1]?.body))).toEqual({ question: 'May baha ba?' })
})

it('askVoice sends the audio as base64 with here, and gives the answer and the transcript', async () => {
  const fetchFn = fetchReplying(json(200, { answer: ANSWER, transcript: 'Baha ba sa España cor. Maceda?' }))

  const result = await askVoice(API, { audio: WAV, here: HERE }, DEVICE, fetchFn)

  expect(result).toEqual({ answer: ANSWER, transcript: 'Baha ba sa España cor. Maceda?' })
  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(`${API}/ask/voice`)
  expect(headersOf(fetchFn).get('X-Lusot-Device')).toBe(DEVICE)
  const body = JSON.parse(String(init?.body))
  expect(body).toEqual({ audio: 'UklGRgD/EIA=', here: HERE })
  expect(Uint8Array.from(atob(body.audio), (c) => c.charCodeAt(0))).toEqual(WAV)
})

it('ask keeps only the answer fields, and drops a report it can\'t word or a demo pin without a credit', async () => {
  const odd = { ...ASK_PIN, id: 'r_0000000000000000000000000000000a', level: 'ankle_deep' }
  const uncredited = { ...ASK_DEMO, id: 'r_0000000000000000000000000000000b', credit: undefined }
  const liveInDemo = { ...ASK_PIN, id: 'r_0000000000000000000000000000000c' }
  const undated = { ...ASK_PIN, id: 'r_0000000000000000000000000000000d', capturedAt: '' }
  const reports = [ASK_PIN, odd, undated]
  const body = { answer: { ...ANSWER, reports, demo: [ASK_DEMO, uncredited, liveInDemo], extra: 'x' }, extra: 'y' }

  const { answer } = await ask(API, { question: 'Baha?' }, DEVICE, fetchReplying(json(200, body)))

  expect(answer).toEqual(ANSWER)
})

it.each([
  ['no answer', {}],
  ['an unknown kind', { answer: { ...ANSWER, kind: 'something_new' } }],
  ['an unknown source', { answer: { ...ANSWER, source: 'free_text' } }],
  ['a crossing that isn\'t a boolean', { answer: { ...ANSWER, crossing: 'yes' } }],
  ['an unknown vehicle', { answer: { ...ANSWER, vehicle: 'suv' } }],
  ['a deepest report it can\'t show', { answer: { ...ANSWER, reports: [{ ...ASK_PIN, level: 'ankle_deep' }] } }],
  ['reports that aren\'t a list', { answer: { ...ANSWER, reports: 'r1' } }],
  ['a place without a name', { answer: { ...ANSWER, place: { source: 'spots' } } }],
  ['reports about no place', { answer: { ...ANSWER, place: null } }],
  ['a deepest report whose time doesn\'t parse', { answer: { ...ANSWER, reports: [{ ...ASK_PIN, capturedAt: 'soon' }] } }],
  ['a deepest report with no floor mark', { answer: { ...ANSWER, reports: [{ ...ASK_PIN, levelIsFloor: undefined }] } }],
  ['a demo pin listed as the deepest report', { answer: { ...ANSWER, reports: [{ ...ASK_DEMO, id: ID }] } }],
])('ask refuses an answer with %s as malformed', async (_name, body) => {
  await expect(ask(API, { question: 'Baha?' }, DEVICE, fetchReplying(json(200, body)))).rejects.toBeInstanceOf(
    MalformedAnswerError,
  )
})

it('askVoice refuses an answer without a transcript as malformed', async () => {
  await expect(askVoice(API, { audio: WAV }, DEVICE, fetchReplying(json(200, { answer: ANSWER })))).rejects.toBeInstanceOf(
    MalformedAnswerError,
  )
})

it.each(['question_limit', 'question_cap'])('a %s is an HttpError with its code and Retry-After, never retried', async (code) => {
  for (const call of [
    (f: typeof fetch) => ask(API, { question: 'Baha?' }, DEVICE, f),
    (f: typeof fetch) => askVoice(API, { audio: WAV }, DEVICE, f),
  ]) {
    const fetchFn = fetchReplying(json(429, { error: code }, { 'retry-after': '1234' }), json(200, { answer: ANSWER }))
    await expect(call(fetchFn)).rejects.toMatchObject({ status: 429, code, isDeviceLimit: true, retryAfterMs: 1_234_000 })
    expect(fetchFn).toHaveBeenCalledOnce()
  }
})

it("a bare 429, API Gateway's throttle, is retried once after 2 s", async () => {
  vi.useFakeTimers()
  const fetchFn = fetchReplying(json(429, { message: 'Too Many Requests' }), json(200, { answer: ANSWER }))

  const pending = ask(API, { question: 'Baha?' }, DEVICE, fetchFn)
  const state = track(pending)
  await vi.advanceTimersByTimeAsync(1999)
  expect(fetchFn).toHaveBeenCalledOnce()
  expect(state.settled).toBe(false)
  await vi.advanceTimersByTimeAsync(1)

  await expect(pending).resolves.toEqual({ answer: ANSWER })
  expect(fetchFn).toHaveBeenCalledTimes(2)

  // A second bare 429 is shown, not retried again.
  const twice = fetchReplying(json(429, {}), json(429, {}), json(200, { answer: ANSWER }))
  const refused = ask(API, { question: 'Baha?' }, DEVICE, twice)
  const caught = refused.catch((err: unknown) => err)
  await vi.advanceTimersByTimeAsync(2000)
  expect(await caught).toMatchObject({ status: 429, code: undefined })
  expect(twice).toHaveBeenCalledTimes(2)
})

it.each(['voice_failed', 'ask_unavailable', 'voice_paused'])('a 503 %s is never retried', async (code) => {
  const fetchFn = fetchReplying(json(503, { error: code }), json(200, { answer: ANSWER, transcript: 'x' }))

  await expect(askVoice(API, { audio: WAV }, DEVICE, fetchFn)).rejects.toMatchObject({ status: 503, code })
  expect(fetchFn).toHaveBeenCalledOnce()
})

it('a network error after the request was sent is never retried', async () => {
  const fetchFn = vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError('Failed to fetch'))
  fetchFn.mockResolvedValueOnce(json(200, { answer: ANSWER }))

  await expect(ask(API, { question: 'Baha?' }, DEVICE, fetchFn)).rejects.toBeInstanceOf(TypeError)
  expect(fetchFn).toHaveBeenCalledOnce()
})

it("ask waits up to 30 s, API Gateway's own limit, then gives a RequestTimeoutError, never retried", async () => {
  vi.useFakeTimers()
  const fetchFn = vi.fn<typeof fetch>(() => new Promise<Response>(() => {}))

  const pending = ask(API, { question: 'Baha?' }, DEVICE, fetchFn)
  const caught = pending.catch((err: unknown) => err)
  const state = track(pending)
  await vi.advanceTimersByTimeAsync(29_999)
  expect(state.settled).toBe(false)
  await vi.advanceTimersByTimeAsync(1)

  expect(await caught).toBeInstanceOf(RequestTimeoutError)
  expect(fetchFn).toHaveBeenCalledOnce()
})

it('isDeviceLimit covers Ask\'s two codes', () => {
  expect(new HttpError(429, 'question_limit').isDeviceLimit).toBe(true)
  expect(new HttpError(429, 'question_cap').isDeviceLimit).toBe(true)
  expect(new HttpError(503, 'voice_failed').isDeviceLimit).toBe(false)
})
