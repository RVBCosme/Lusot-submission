import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { HttpError, RequestTimeoutError, requestUpload } from './api'
import { retryOnce } from './retry'

const API = 'https://api.example.test'
const ID = 'r_0123456789abcdef0123456789abcdef'
const DEVICE = '0f8e4a52-3c1d-4b7a-9e26-5d0c8b1f7a43'
const REQ = {
  lat: 14.6095,
  lng: 120.9894,
  gpsAccuracyM: 12,
  capturedAt: '2026-10-30T10:05:12.000Z',
  nudgeM: 0,
  consentVersion: '3f9a1c07',
}
const UPLOAD = { url: 'https://lusot-test01-uploads.s3.ap-southeast-1.amazonaws.com/', fields: { key: `raw/${ID}.jpg` } }

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

const created = () => json(201, { reportId: ID, upload: UPLOAD, expiresInS: 300 })

// Lets a test advance the fake clock past a promise's rejection without an unhandled rejection.
function settle<T>(promise: Promise<T>): Promise<{ value?: T; error?: unknown }> {
  return promise.then(
    (value) => ({ value }),
    (error: unknown) => ({ error }),
  )
}

// The first answer of a POST /uploads that failed in a way worth one more try (C635).
const RETRIED: [string, () => Promise<Response>][] = [
  ['a 503', async () => json(503, { message: 'Service Unavailable' })],
  ['a throttling 429', async () => json(429, { message: 'Too Many Requests' })],
  ['a network TypeError', () => Promise.reject(new TypeError('Failed to fetch'))],
]

it.each(RETRIED)('retryOnce calls twice on %s, about 2 s later', async (_, first) => {
  const fetchFn = vi.fn<typeof fetch>().mockImplementationOnce(first).mockResolvedValueOnce(created())

  const upload = settle(retryOnce(() => requestUpload(API, REQ, DEVICE, fetchFn)))
  await vi.advanceTimersByTimeAsync(1999)
  expect(fetchFn).toHaveBeenCalledOnce()
  await vi.advanceTimersByTimeAsync(1)

  expect(fetchFn).toHaveBeenCalledTimes(2)
  expect((await upload).value).toEqual({ reportId: ID, upload: UPLOAD })
})

it('retryOnce retries a timeout', async () => {
  const fetchFn = vi
    .fn<typeof fetch>()
    .mockImplementationOnce(() => new Promise<Response>(() => {}))
    .mockResolvedValueOnce(created())

  const upload = settle(retryOnce(() => requestUpload(API, REQ, DEVICE, fetchFn)))
  // The first request gives up at 15 s with RequestTimeoutError; the retry comes 2 s after.
  await vi.advanceTimersByTimeAsync(16_999)
  expect(fetchFn).toHaveBeenCalledOnce()
  await vi.advanceTimersByTimeAsync(1)

  expect(fetchFn).toHaveBeenCalledTimes(2)
  expect((await upload).value).toEqual({ reportId: ID, upload: UPLOAD })
})

it('retryOnce retries only once', async () => {
  const fetchFn = vi.fn<typeof fetch>(async () => json(503, { message: 'Service Unavailable' }))

  const upload = settle(retryOnce(() => requestUpload(API, REQ, DEVICE, fetchFn)))
  await vi.advanceTimersByTimeAsync(60_000)

  expect(fetchFn).toHaveBeenCalledTimes(2)
  expect((await upload).error).toMatchObject({ status: 503 })
})

it('retryOnce throws the second error', async () => {
  let calls = 0
  const call = async () => {
    calls += 1
    throw calls === 1 ? new TypeError('Failed to fetch') : new RequestTimeoutError(15_000)
  }

  const result = settle(retryOnce(call))
  await vi.advanceTimersByTimeAsync(2000)

  expect((await result).error).toBeInstanceOf(RequestTimeoutError)
  expect(calls).toBe(2)
})

it.each([
  ['a 503 uploads_paused', 503, { error: 'uploads_paused' }, false],
  ['a 400', 400, { error: 'bad_request', detail: 'body must be JSON' }, false],
  ['a 422', 422, { error: 'capture_too_old' }, false],
  ['a 429 device_limit', 429, { error: 'device_limit' }, true],
  ['a 429 global_cap', 429, { error: 'global_cap' }, true],
  ['a 429 question_limit', 429, { error: 'question_limit' }, true],
  ['a 429 question_cap', 429, { error: 'question_cap' }, true],
])('retryOnce calls once on %s', async (_, status, body, isDeviceLimit) => {
  const fetchFn = vi.fn<typeof fetch>().mockResolvedValueOnce(json(status, body)).mockResolvedValueOnce(created())

  const upload = settle(retryOnce(() => requestUpload(API, REQ, DEVICE, fetchFn)))
  await vi.advanceTimersByTimeAsync(60_000)
  const { error } = await upload

  expect(fetchFn).toHaveBeenCalledOnce()
  expect(error).toBeInstanceOf(HttpError)
  expect(error).toMatchObject({ status, code: body.error, isDeviceLimit })
})

it('retryOnce never retries an error it does not know', async () => {
  const call = vi.fn(async () => {
    throw new Error('something else')
  })

  const result = settle(retryOnce(call))
  await vi.advanceTimersByTimeAsync(60_000)

  expect((await result).error).toMatchObject({ message: 'something else' })
  expect(call).toHaveBeenCalledOnce()
})

it('retryOnce takes its delay and sleep', async () => {
  vi.useRealTimers()
  const sleep = vi.fn(async (_ms: number) => {})
  const call = vi
    .fn<() => Promise<string>>()
    .mockRejectedValueOnce(new HttpError(503))
    .mockResolvedValueOnce('sent')

  expect(await retryOnce(call, { delayMs: 500, sleep })).toBe('sent')
  expect(sleep.mock.calls).toEqual([[500]])
})

it('retryOnce gives the first answer when it succeeds', async () => {
  const call = vi.fn(async () => 'sent')

  expect(await retryOnce(call)).toBe('sent')
  expect(call).toHaveBeenCalledOnce()
})
