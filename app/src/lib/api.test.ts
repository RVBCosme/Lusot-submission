import { afterEach, expect, it, vi } from 'vitest'
import { apiBaseUrl, HttpError, pollReport, PollTimeoutError, postToS3, requestUpload } from './api'

const API = 'https://api.example.test'
const ID = 'r_0123456789abcdef0123456789abcdef'
const NOW = Date.parse('2026-10-30T10:06:40Z')
const REQ = { lat: 14.6095, lng: 120.9894, gpsAccuracyM: 12, capturedAt: '2026-10-30T10:05:12.000Z' }
const UPLOAD = {
  url: 'https://lusot-test01-uploads.s3.ap-southeast-1.amazonaws.com/',
  fields: { 'Content-Type': 'image/jpeg', key: `raw/${ID}.jpg`, Policy: 'cG9saWN5', 'X-Amz-Signature': 'c2lnbmF0dXJl' },
}

afterEach(() => {
  vi.useRealTimers()
})

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

function report(status: string, refusalReason?: string): Response {
  return json(200, { reportId: ID, status, refusalReason, capturedAt: '2026-10-30T10:05:12Z' })
}

// A fetch that answers each call with the next response.
function fetchReplying(...responses: Response[]) {
  const fetchFn = vi.fn<typeof fetch>()
  for (const response of responses) fetchFn.mockResolvedValueOnce(response)
  return fetchFn
}

function noSleep() {
  return vi.fn((_ms: number) => Promise.resolve())
}

// A sleep that moves the mocked clock instead of waiting, so the poll deadline runs on test time.
function clockSleep() {
  vi.setSystemTime(NOW)
  return vi.fn(async (ms: number) => {
    vi.setSystemTime(Date.now() + ms)
  })
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

it('apiBaseUrl drops trailing slashes and is empty when VITE_API_URL is unset', () => {
  expect(apiBaseUrl('https://api.example.test')).toBe('https://api.example.test')
  expect(apiBaseUrl('https://api.example.test//')).toBe('https://api.example.test')
  expect(apiBaseUrl('')).toBe('')
  expect(apiBaseUrl(undefined)).toBe('')
})

it('requestUpload posts the fix and capture time as JSON', async () => {
  const fetchFn = fetchReplying(json(201, { reportId: ID, upload: UPLOAD, expiresInS: 300 }))

  const result = await requestUpload(API, REQ, fetchFn)

  expect(result).toEqual({ reportId: ID, upload: UPLOAD })
  expect(fetchFn).toHaveBeenCalledOnce()
  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe(`${API}/uploads`)
  expect(init?.method).toBe('POST')
  expect(new Headers(init?.headers).get('content-type')).toBe('application/json')
  expect(JSON.parse(String(init?.body))).toEqual(REQ)
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

it('pollReport resolves on a final status', async () => {
  const fetchFn = fetchReplying(report('pending'), report('pending'), report('failed', 'pipeline_not_built'))
  const sleep = noSleep()

  const result = await pollReport(API, ID, undefined, fetchFn, sleep)

  expect(result).toEqual({ status: 'failed', refusalReason: 'pipeline_not_built' })
  expect(sleep.mock.calls).toEqual([[2000], [2000]])
  expect(fetchFn.mock.calls.map(([url]) => url)).toEqual(Array(3).fill(`${API}/reports/${ID}`))
})

it('pollReport keeps polling while processing', async () => {
  const fetchFn = fetchReplying(report('pending'), report('processing'), report('failed', 'pipeline_not_built'))
  const sleep = noSleep()

  const result = await pollReport(API, ID, undefined, fetchFn, sleep)

  expect(result).toEqual({ status: 'failed', refusalReason: 'pipeline_not_built' })
  expect(sleep.mock.calls).toEqual([[2000], [2000]])
})

it('pollReport keeps polling through a 404', async () => {
  // The reports index is eventually consistent, so a fresh report can briefly 404.
  const fetchFn = fetchReplying(json(404, { error: 'not_found' }), report('pending'), report('failed', 'pipeline_not_built'))
  const sleep = noSleep()

  const result = await pollReport(API, ID, undefined, fetchFn, sleep)

  expect(result).toEqual({ status: 'failed', refusalReason: 'pipeline_not_built' })
  expect(sleep).toHaveBeenCalledTimes(2)
})

it('pollReport returns the result fields', async () => {
  // A knee reading from a wheel and a person, as GET /reports/{id} returns it (C67).
  const fields = {
    status: 'done',
    noFloodSeen: false,
    level: 'knee',
    landmark: 'rim_three_quarters',
    passability: 'NPLV',
    basis: { vehicles: 1, people: 1 },
    levelIsFloor: false,
  }
  const fetchFn = fetchReplying(json(200, { reportId: ID, ...fields, capturedAt: '2026-10-30T10:05:12Z' }))

  const result = await pollReport(API, ID, undefined, fetchFn, noSleep())

  // Only the result: reportId and capturedAt stay behind, as in MS1.
  expect(result).toEqual(fields)
})

it('pollReport times out with a clear error', async () => {
  const fetchFn = vi.fn<typeof fetch>(async () => report('pending'))
  const sleep = clockSleep()

  const poll = pollReport(API, ID, { intervalMs: 2000, timeoutMs: 6000 }, fetchFn, sleep)

  await expect(poll).rejects.toThrow(`No result for report ${ID} after 6 s`)
  // Its own class, so the screen can read a timeout as processing failed (spec §3.8).
  await expect(poll).rejects.toBeInstanceOf(PollTimeoutError)
  expect(sleep).toHaveBeenCalledTimes(3)
  expect(fetchFn).toHaveBeenCalledTimes(4)
})

it('pollReport gives up when 404s run into the deadline', async () => {
  const fetchFn = vi.fn<typeof fetch>(async () => json(404, { error: 'not_found' }))
  const sleep = clockSleep()

  await expect(pollReport(API, ID, { intervalMs: 2000, timeoutMs: 6000 }, fetchFn, sleep)).rejects.toThrow(
    `No result for report ${ID} after 6 s`,
  )
  expect(fetchFn).toHaveBeenCalledTimes(4)
})

it('pollReport waits 120 s by default', async () => {
  const fetchFn = vi.fn<typeof fetch>(async () => report('pending'))
  const sleep = clockSleep()

  await expect(pollReport(API, ID, undefined, fetchFn, sleep)).rejects.toThrow(`No result for report ${ID} after 120 s`)
  expect(sleep).toHaveBeenCalledTimes(60)
  expect(fetchFn).toHaveBeenCalledTimes(61)
})

it("pollReport's deadline counts the time requests take", async () => {
  const sleep = clockSleep()
  // Each answer takes 10 s to arrive.
  const fetchFn = vi.fn<typeof fetch>(async () => {
    vi.setSystemTime(Date.now() + 10_000)
    return report('pending')
  })

  await expect(pollReport(API, ID, { intervalMs: 2000, timeoutMs: 30_000 }, fetchFn, sleep)).rejects.toThrow(
    `No result for report ${ID} after 30 s`,
  )
  expect(fetchFn).toHaveBeenCalledTimes(3)
})

it('requests give up on a stalled connection', async () => {
  vi.useFakeTimers()
  const stalled = vi.fn<typeof fetch>(() => new Promise<Response>(() => {}))
  const jpeg = new Blob(['jpeg bytes'], { type: 'image/jpeg' })

  const upload = track(requestUpload(API, REQ, stalled))
  const poll = track(pollReport(API, ID, undefined, stalled, noSleep()))
  const s3 = track(postToS3(UPLOAD, jpeg, stalled))

  await vi.advanceTimersByTimeAsync(14_999)
  expect([upload.settled, poll.settled, s3.settled]).toEqual([false, false, false])
  await vi.advanceTimersByTimeAsync(1)
  expect(upload.error).toEqual(new Error('No answer after 15 s'))
  expect(poll.error).toEqual(new Error('No answer after 15 s'))
  // The photo upload gets longer.
  expect(s3.settled).toBe(false)
  await vi.advanceTimersByTimeAsync(45_000)
  expect(s3.error).toEqual(new Error('No answer after 60 s'))
  // Each stalled request is aborted too, which frees the connection.
  expect(stalled.mock.calls.map(([, init]) => init?.signal?.aborted)).toEqual([true, true, true])
})

it('non-2xx responses throw with the status', async () => {
  const refused = requestUpload(API, REQ, fetchReplying(json(422, { error: 'capture_too_old' })))
  await expect(refused).rejects.toThrow('HTTP 422 capture_too_old')
  await expect(refused).rejects.toBeInstanceOf(HttpError)
  await expect(refused).rejects.toMatchObject({ status: 422, code: 'capture_too_old' })

  // S3 answers in XML, so only the status is named.
  const denied = new Response('<Error><Code>AccessDenied</Code></Error>', { status: 403 })
  const jpeg = new Blob(['jpeg bytes'], { type: 'image/jpeg' })
  await expect(postToS3(UPLOAD, jpeg, fetchReplying(denied))).rejects.toThrow('HTTP 403')

  const broken = fetchReplying(json(500, { error: 'internal' }))
  await expect(pollReport(API, ID, undefined, broken, noSleep())).rejects.toThrow('HTTP 500 internal')
})

it("a 400 names the API's detail", async () => {
  const detail = 'lat must be a number from -90 to 90'
  const invalid = requestUpload(API, REQ, fetchReplying(json(400, { error: 'bad_request', detail })))

  await expect(invalid).rejects.toThrow(`HTTP 400 bad_request: ${detail}`)
  await expect(invalid).rejects.toMatchObject({ status: 400, code: 'bad_request', detail })
})
