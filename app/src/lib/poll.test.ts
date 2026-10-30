import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { HttpError } from './api'
import { intervalAt, POLL, pollReport, PollTimeoutError } from './poll'

const API = 'https://api.example.test'
const ID = 'r_0123456789abcdef0123456789abcdef'
const NOW = Date.parse('2026-10-30T10:06:40Z')

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', ...headers } })
}

function report(status: string, fields: Record<string, unknown> = {}): Response {
  return json(200, { reportId: ID, status, capturedAt: '2026-10-30T10:05:12Z', mode: 'live', published: false, ...fields })
}

type Answer = Response | Error | 'stall'

// A fetch that notes the fake clock's time of each call (ms since the test began) and gives each answer in
// turn, then the last answer again. An Error rejects, as a network error does; 'stall' never answers.
function fetchAnswering(...answers: Answer[]) {
  const times: number[] = []
  const fetchFn = vi.fn<typeof fetch>(() => {
    times.push(Date.now() - NOW)
    const answer = answers.length > 1 ? answers.shift()! : answers[0]
    if (answer === 'stall') return new Promise<Response>(() => {})
    if (answer instanceof Error) return Promise.reject(answer)
    // A new Response each time, since a body reads once.
    return Promise.resolve(answer.clone())
  })
  return { fetchFn, times }
}

// From first to last inclusive, every step ms.
function range(first: number, last: number, step: number): number[] {
  return Array.from({ length: (last - first) / step + 1 }, (_, i) => first + i * step)
}

// Lets a test advance the fake clock past a promise's rejection without an unhandled rejection.
function settle<T>(promise: Promise<T>): Promise<{ value?: T; error?: unknown }> {
  return promise.then(
    (value) => ({ value }),
    (error: unknown) => ({ error }),
  )
}

it('POLL holds the schedule', () => {
  expect(POLL).toEqual({ fastMs: 2000, fastForMs: 60_000, midMs: 5000, midForMs: 240_000, slowMs: 15_000, windowMs: 600_000 })
})

it('intervalAt steps from 2 s to 5 s at 60 s, and to 15 s at 240 s', () => {
  expect(intervalAt(0)).toBe(2000)
  expect(intervalAt(59_999)).toBe(2000)
  expect(intervalAt(60_000)).toBe(5000)
  expect(intervalAt(239_999)).toBe(5000)
  expect(intervalAt(240_000)).toBe(15_000)
  expect(intervalAt(600_000)).toBe(15_000)
})

it('pollReport polls every 2 s, then every 5 s, then every 15 s, until 600 s', async () => {
  const { fetchFn, times } = fetchAnswering(report('pending'))

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(600_000)
  const { error } = await poll

  expect(times).toEqual([...range(0, 58_000, 2000), ...range(60_000, 240_000, 5000), ...range(255_000, 600_000, 15_000)])
  expect(times).toHaveLength(91)
  expect(error).toBeInstanceOf(PollTimeoutError)
  // Read as "no result yet", never a failure, and the report id stays out of the message.
  expect((error as Error).message).not.toContain('r_')
  expect((error as Error).message).not.toContain(ID)
})

it('pollReport ends at 600 s even when requests take time', async () => {
  // Each answer takes 3 s to arrive; the deadline is on the clock, so their time counts too.
  const times: number[] = []
  const fetchFn = vi.fn<typeof fetch>(async () => {
    times.push(Date.now() - NOW)
    await new Promise((resolve) => setTimeout(resolve, 3000))
    return report('pending')
  })

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(603_000)

  expect((await poll).error).toBeInstanceOf(PollTimeoutError)
  // The last poll starts at the deadline, never after it.
  expect(times.at(-1)).toBe(600_000)
  expect(times.every((t) => t <= 600_000)).toBe(true)
})

it('"Check again" polls every 15 s for another 600 s', async () => {
  const { fetchFn, times } = fetchAnswering(report('processing'))

  const poll = settle(pollReport(API, ID, { fetchFn, startElapsedMs: 240_000 }))
  await vi.advanceTimersByTimeAsync(600_000)

  expect(times).toEqual(range(0, 600_000, 15_000))
  expect(times).toHaveLength(41)
  expect((await poll).error).toBeInstanceOf(PollTimeoutError)
})

it('pollReport resolves on a final status with the report fields', async () => {
  const done = {
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
  }
  const { fetchFn, times } = fetchAnswering(report('pending'), report('processing'), json(200, done))

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(4000)

  expect(await poll).toEqual({ value: done })
  expect(times).toEqual([0, 2000, 4000])
  expect(fetchFn.mock.calls.map(([url]) => url)).toEqual(Array(3).fill(`${API}/reports/${ID}`))
})

it.each(['refused', 'failed'])('pollReport resolves on %s', async (status) => {
  const { fetchFn } = fetchAnswering(report(status, { refusalReason: 'water_unsure' }))

  const { value } = await settle(pollReport(API, ID, { fetchFn }))

  expect(value).toMatchObject({ status, refusalReason: 'water_unsure' })
})

it('a 503, a network error and a 404 keep polling', async () => {
  const { fetchFn, times } = fetchAnswering(
    json(503, { message: 'Service Unavailable' }),
    new TypeError('Failed to fetch'),
    json(404, { error: 'not_found' }),
    json(500, { error: 'internal' }),
    report('done', { noFloodSeen: true }),
  )

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(8000)

  expect((await poll).value).toMatchObject({ status: 'done', noFloodSeen: true })
  expect(times).toEqual([0, 2000, 4000, 6000, 8000])
})

it('a request timeout keeps polling', async () => {
  const { fetchFn, times } = fetchAnswering('stall', report('done', { noFloodSeen: true }))

  const poll = settle(pollReport(API, ID, { fetchFn }))
  // The stalled request gives up at 15 s, and the next poll comes an interval later.
  await vi.advanceTimersByTimeAsync(17_000)

  expect((await poll).value).toMatchObject({ status: 'done' })
  expect(times).toEqual([0, 17_000])
})

it('an answer that is not JSON keeps polling', async () => {
  // A captive portal's page, say: not a failure the server reported.
  const portal = new Response('<html>Sign in to Wi-Fi</html>', { status: 200, headers: { 'content-type': 'text/html' } })
  const { fetchFn, times } = fetchAnswering(portal, report('done', { noFloodSeen: true }))

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(2000)

  expect((await poll).value).toMatchObject({ status: 'done' })
  expect(times).toEqual([0, 2000])
})

it('a 400 throws HttpError', async () => {
  const { fetchFn } = fetchAnswering(json(400, { error: 'bad_request' }), report('done'))

  const { error } = await settle(pollReport(API, ID, { fetchFn }))

  expect(error).toBeInstanceOf(HttpError)
  expect(error).toMatchObject({ status: 400, code: 'bad_request' })
  expect(fetchFn).toHaveBeenCalledOnce()
})

it('a 429 with a readable Retry-After waits its seconds', async () => {
  const { fetchFn, times } = fetchAnswering(
    json(429, { message: 'Too Many Requests' }, { 'retry-after': '7' }),
    report('done', { noFloodSeen: true }),
  )

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(6999)
  expect(times).toEqual([0])
  await vi.advanceTimersByTimeAsync(1)

  expect(times).toEqual([0, 7000])
  expect((await poll).value).toMatchObject({ status: 'done' })
})

it('a 429 with a long Retry-After waits only to the deadline', async () => {
  const { fetchFn, times } = fetchAnswering(json(429, {}, { 'retry-after': '9999' }), report('pending'))

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(600_000)

  // One last poll at the deadline, then "no result yet".
  expect(times).toEqual([0, 600_000])
  expect((await poll).error).toBeInstanceOf(PollTimeoutError)
})

it('a 429 without a readable Retry-After waits the interval plus jitter', async () => {
  const { fetchFn, times } = fetchAnswering(json(429, { message: 'Too Many Requests' }), report('done', { noFloodSeen: true }))

  const poll = settle(pollReport(API, ID, { fetchFn, random: () => 0.25 }))
  await vi.advanceTimersByTimeAsync(2250)

  expect(times).toEqual([0, 2250])
  expect((await poll).value).toMatchObject({ status: 'done' })
})

it('a 429 with Retry-After: 0 still waits the interval', async () => {
  // Never sooner than the schedule, so a zero can't make the poll hammer the API.
  const { fetchFn, times } = fetchAnswering(json(429, {}, { 'retry-after': '0' }), report('done', { noFloodSeen: true }))

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(2000)

  expect(times).toEqual([0, 2000])
  expect((await poll).value).toMatchObject({ status: 'done' })
})

it('an aborted signal stops the loop before the next fetch', async () => {
  const { fetchFn } = fetchAnswering(report('pending'))
  const controller = new AbortController()

  const poll = settle(pollReport(API, ID, { fetchFn, signal: controller.signal }))
  await vi.advanceTimersByTimeAsync(1000)
  controller.abort()
  const { error } = await poll
  await vi.advanceTimersByTimeAsync(60_000)

  expect(error).toMatchObject({ name: 'AbortError' })
  expect(fetchFn).toHaveBeenCalledOnce()
})

it('a signal aborted before the start fetches nothing', async () => {
  const { fetchFn } = fetchAnswering(report('pending'))
  const controller = new AbortController()
  controller.abort()

  const { error } = await settle(pollReport(API, ID, { fetchFn, signal: controller.signal }))

  expect(error).toMatchObject({ name: 'AbortError' })
  expect(fetchFn).not.toHaveBeenCalled()
})

it('a signal aborted during a fetch drops its answer', async () => {
  const controller = new AbortController()
  const fetchFn = vi.fn<typeof fetch>(async () => {
    controller.abort()
    return report('done', { noFloodSeen: true })
  })

  const { error } = await settle(pollReport(API, ID, { fetchFn, signal: controller.signal }))

  expect(error).toMatchObject({ name: 'AbortError' })
})

it('an injected sleep, clock and jitter drive the schedule', async () => {
  vi.useRealTimers()
  let clock = 0
  const sleep = vi.fn(async (ms: number) => {
    clock += ms
  })
  const { fetchFn } = fetchAnswering(json(429, { message: 'Too Many Requests' }), report('pending'), report('done'))

  const result = await pollReport(API, ID, { fetchFn, sleep, now: () => clock, random: () => 0.5, startElapsedMs: 59_000 })

  expect(result).toMatchObject({ status: 'done' })
  // 59 s: the 2 s interval plus 500 ms of jitter; then at 61.5 s, the 5 s interval.
  expect(sleep.mock.calls.map(([ms]) => ms)).toEqual([2500, 5000])
})

it('pollReport logs nothing', async () => {
  const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((name) =>
    vi.spyOn(console, name).mockImplementation(() => {}),
  )
  const { fetchFn } = fetchAnswering(
    json(503, { message: 'Service Unavailable' }),
    new TypeError('Failed to fetch'),
    json(429, {}, { 'retry-after': '3' }),
    report('done', { level: 'knee', landmark: 'knee', passability: 'NPLV', basis: { vehicles: 0, people: 1 } }),
  )

  const poll = settle(pollReport(API, ID, { fetchFn }))
  await vi.advanceTimersByTimeAsync(10_000)
  await poll

  for (const spy of spies) expect(spy).not.toHaveBeenCalled()
})
