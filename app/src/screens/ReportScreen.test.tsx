import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { LanguageProvider } from '../i18n'
import { EN, type StringKey } from '../i18n/en'
import { Layout } from '../layout/Layout'
import type { Pin } from '../lib/api'
import { GateProvider, NOTICE_VERSION, NoticeGate } from '../lib/consent'
import { getDeviceId } from '../lib/device'
import { PoorFix, waitForFix, type Fix } from '../lib/geo'
import { POLL, pollReport } from '../lib/poll'
import { MOCK_FILES_ORIGIN, type Scenario } from '../mock/fixtures'
import { createMockFetch } from '../mock/mockFetch'
import type { FlowState, OwnPin } from '../report/flow'
import { ReportFlowProvider, useOwnPin, useReportFlow, useSeenOnMap } from '../report/ReportFlowProvider'
import { useRoute } from '../router'
import { deferred, fakeStream, showFrame, stubCanvas } from '../test/camera'
import { ReportScreen } from './ReportScreen'

// The app's fetch, swapped per test for a recording fake in front of Task 6's mock API.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))
// The location watch, answered by hand.
vi.mock('../lib/geo', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/geo')>()),
  waitForFix: vi.fn(),
}))
// The real poll, watched.
vi.mock('../lib/poll', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/poll')>()
  return { ...actual, pollReport: vi.fn(actual.pollReport) }
})

const API = 'https://api.example.test'
const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
const T0 = Date.parse('2026-10-30T09:15:30.000Z')
const FIX: Fix = { lat: 14.6123456, lng: 121.0456789, accuracyM: 12 }
const KNEE_LINE = 'Knee deep at this spot (MMDA level).'

const text = (key: StringKey) => EN[key].text
const getUserMedia = vi.fn<(constraints: MediaStreamConstraints) => Promise<MediaStream>>()
let fixes: ReturnType<typeof deferred<Fix>>[] = []

// ---- the fake API ----

type Kind = 'upload' | 's3' | 'report' | 'other'
type Scripted = Response | Error | 'hang' | ((url: string) => Response | Promise<Response>)
type Call = { kind: Kind; url: string; init?: RequestInit }

const reply = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })

// Each kind of call takes its scripted answers in order, then Task 6's mock answers.
function fakeApi(scenario: Scenario = 'level_knee', script: Partial<Record<Kind, Scripted[]>> = {}) {
  const base = createMockFetch({ scenario, now: () => Date.now() })
  const calls: Call[] = []
  const queues: Record<Kind, Scripted[]> = {
    upload: [...(script.upload ?? [])],
    s3: [...(script.s3 ?? [])],
    report: [...(script.report ?? [])],
    other: [],
  }
  net.fetch = async (input, init) => {
    const url = String(input)
    const method = (init?.method ?? 'GET').toUpperCase()
    const kind: Kind =
      method === 'POST' && url === `${API}/uploads`
        ? 'upload'
        : url.startsWith(`${MOCK_FILES_ORIGIN}/uploads/`)
          ? 's3'
          : url.startsWith(`${API}/reports/`)
            ? 'report'
            : 'other'
    calls.push({ kind, url, init })
    const next = queues[kind].shift()
    if (next === undefined) return base(input, init)
    if (next === 'hang') {
      return new Promise<Response>((_, reject) =>
        init?.signal?.addEventListener('abort', () => reject(new DOMException('stopped', 'AbortError'))),
      )
    }
    if (next instanceof Error) throw next
    if (next instanceof Response) return next
    return next(url)
  }
  const of = (kind: Kind) => calls.filter((call) => call.kind === kind)
  const uploadBody = (n = 0) => JSON.parse(String(of('upload')[n]?.init?.body)) as Record<string, unknown>
  const reportId = () => of('report')[0]?.url.split('/').pop() ?? ''
  return { calls, of, uploadBody, reportId }
}

// ---- the screens ----

// What the provider holds, read by a probe beside the screens.
const seen: { state?: FlowState; pin?: OwnPin; seenOnMap?: (pins: readonly Pin[]) => void } = {}
function Probe() {
  const { state } = useReportFlow()
  const pin = useOwnPin()
  const seenOnMap = useSeenOnMap()
  useEffect(() => {
    seen.state = state
    seen.pin = pin
    seen.seenOnMap = seenOnMap
  })
  return null
}

// The app's tree, as App builds it, with the probe.
function Harness() {
  const route = useRoute()
  return (
    <LanguageProvider>
      <ReportFlowProvider apiUrl={API}>
        <Probe />
        <Layout route={route} apiReady>
          <GateProvider>
            {route.name === 'report' ? (
              <NoticeGate>
                <ReportScreen apiUrl={API} />
              </NoticeGate>
            ) : (
              <h1>Elsewhere</h1>
            )}
          </GateProvider>
        </Layout>
      </ReportFlowProvider>
    </LanguageProvider>
  )
}

const flush = () => act(async () => {})
// Lets the clock run, with every promise and render it sets off.
const advance = async (ms: number) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}
const settle = () => advance(0)
const video = () => document.querySelector('video') as HTMLVideoElement
const button = (key: StringKey) => screen.getByRole('button', { name: text(key) }) as HTMLButtonElement
const queryButton = (key: StringKey) => screen.queryByRole('button', { name: text(key) })
const shows = (key: StringKey) => screen.queryAllByText(text(key), { exact: false }).length > 0
const heading = () => screen.getByRole('heading', { level: 1 })
// A link inside the screen, apart from the nav's links of the same name.
const mainLink = (key: StringKey) => within(screen.getByRole('main')).getByRole('link', { name: text(key) })

function go(hash: string) {
  act(() => {
    history.pushState(null, '', `/${hash}`)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
}

function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'))
  })
}

async function openCamera(width = 1920, height = 1080) {
  await flush()
  await act(async () => showFrame(video(), width, height))
}

// The canvas is stubbed for the shutter only: the mock API draws its own pictures with jsdom's canvas afterwards.
async function shoot() {
  stubCanvas()
  fireEvent.click(button('camera.shutter'))
  await settle()
  vi.mocked(HTMLCanvasElement.prototype.getContext).mockRestore()
  vi.mocked(HTMLCanvasElement.prototype.toBlob).mockRestore()
}

// The place step, with the photo taken at T0 and a good fix.
async function reachPlace({ app = false, fix = FIX, width = 1920, height = 1080 } = {}) {
  render(app ? <App apiUrl={API} /> : <Harness />)
  await openCamera(width, height)
  await shoot()
  await act(async () => fixes.at(-1)?.resolve(fix))
}

async function send() {
  fireEvent.click(button('place.send'))
  await settle()
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] })
  vi.setSystemTime(T0)
  getUserMedia.mockReset()
  getUserMedia.mockImplementation(async () => fakeStream().stream)
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, writable: true, value: { getUserMedia } })
  fixes = []
  vi.mocked(waitForFix).mockReset()
  vi.mocked(waitForFix).mockImplementation(() => {
    const fix = deferred<Fix>()
    fixes.push(fix)
    return fix.promise
  })
  vi.mocked(pollReport).mockClear()
  localStorage.setItem('lusot.consent', JSON.stringify({ adult: true, notice: NOTICE_VERSION }))
  history.replaceState(null, '', '/#/report')
  for (const key of Object.keys(seen) as (keyof typeof seen)[]) delete seen[key]
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
  localStorage.clear()
  history.replaceState(null, '', '/')
  document.documentElement.removeAttribute('lang')
  Reflect.deleteProperty(document, 'visibilityState')
})

describe('the gates', () => {
  it('opening #/report directly shows the notice, asks for no camera, and the heading takes focus after "Continue"', async () => {
    localStorage.clear()
    fakeApi()
    render(<App apiUrl={API} />)
    await flush()

    expect(screen.getByTestId('notice')).toBeTruthy()
    expect(getUserMedia).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(button('consent.continue'))
    await flush()

    expect(heading().textContent).toBe(text('camera.title'))
    expect(document.activeElement).toBe(heading())
    expect(getUserMedia).toHaveBeenCalledOnce()
  })

  it('send checks the notice again before any upload, and uploads once after "Continue"', async () => {
    const api = fakeApi()
    await reachPlace()
    localStorage.removeItem('lusot.consent')

    await send()
    expect(api.of('upload')).toHaveLength(0)
    expect(screen.getByTestId('notice')).toBeTruthy()

    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(button('consent.continue'))
    await settle()
    expect(api.of('upload')).toHaveLength(1)
  })

  it('no upload without an API address: a typed #/report is refused with a plain line, and nothing starts', async () => {
    const api = fakeApi()
    render(<App apiUrl="" />)
    await flush()

    expect(shows('report.noApi')).toBe(true)
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(waitForFix).not.toHaveBeenCalled()
    expect(api.calls).toHaveLength(0)
  })
})

describe('the whole path', () => {
  it('opens the camera, then the location watch, then uploads once, polls and ends on the result card', async () => {
    const api = fakeApi()
    render(<Harness />)
    await flush()
    expect(getUserMedia).toHaveBeenCalledOnce()
    // the location watch starts after the camera opens
    expect(waitForFix).not.toHaveBeenCalled()
    await act(async () => showFrame(video()))
    expect(waitForFix).toHaveBeenCalledOnce()

    await shoot()
    await act(async () => fixes[0]?.resolve(FIX))
    expect(heading().textContent).toBe(text('place.title'))
    await send()

    expect(api.of('upload')).toHaveLength(1)
    expect(api.uploadBody()).toEqual({
      lat: FIX.lat,
      lng: FIX.lng,
      gpsAccuracyM: FIX.accuracyM,
      capturedAt: new Date(T0).toISOString(),
      nudgeM: 0,
      consentVersion: NOTICE_VERSION,
    })
    expect(new Headers(api.of('upload')[0]?.init?.headers).get('X-Lusot-Device')).toBe(getDeviceId())
    const s3 = api.of('s3')
    expect(s3).toHaveLength(1)
    const form = s3[0]?.init?.body
    expect(form).toBeInstanceOf(FormData)
    expect((form as FormData).get('file')).toBeInstanceOf(Blob)
    expect(api.calls.map((call) => call.kind).slice(0, 3)).toEqual(['upload', 's3', 'report'])

    await advance(POLL.fastMs * 3)
    expect(screen.getByText(KNEE_LINE)).toBeTruthy()
    expect(heading().textContent).toBe(text('report.resultTitle'))
    expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
  })

  it('send twice uploads once: two clicks in the same moment make one requestUpload', async () => {
    const api = fakeApi()
    await reachPlace()
    const sendNow = button('place.send')

    act(() => {
      sendNow.click()
      sendNow.click()
    })
    await settle()
    await advance(10_000)

    expect(api.of('upload')).toHaveLength(1)
    expect(api.of('s3')).toHaveLength(1)
  })

  it('the waiting step shows the elapsed seconds, and from 60 s that other photos may be ahead, with no time promised', async () => {
    fakeApi('pending_forever')
    await reachPlace()
    await send()

    expect(heading().textContent).toBe(text('report.waitingTitle'))
    // Nothing on the screen is busy, so a screen reader announces the queue note when it comes.
    expect(document.querySelector('[aria-busy="true"]')).toBeNull()
    await advance(59_000)
    expect(screen.getByText(EN['report.elapsed'].text.replace('{seconds}', '59'))).toBeTruthy()
    expect(shows('report.queue')).toBe(false)
    await advance(1_000)
    expect(screen.getByText(text('report.queue'))).toBeTruthy()
    expect(text('report.queue')).not.toMatch(/\d/)
    expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
  })

  it('when the photo is sent, focus moves from the sending heading to the waiting heading', async () => {
    const hold = deferred<void>()
    fakeApi('pending_forever', { s3: [() => hold.promise.then(() => reply(204))] })
    await reachPlace()
    await send()
    const sendingHeading = heading()
    expect(sendingHeading.textContent).toBe(text('report.sendingTitle'))
    expect(document.activeElement).toBe(sendingHeading)

    await act(async () => hold.resolve())
    await settle()
    expect(heading().textContent).toBe(text('report.waitingTitle'))
    expect(heading()).not.toBe(sendingHeading)
    expect(document.activeElement).toBe(heading())
  })
})

describe('retries (pay once)', () => {
  it.each([
    ['a network error', new TypeError('Failed to fetch') as Scripted, 0],
    ['a request timeout', 'hang' as Scripted, 60_000],
  ])('%s on the S3 upload retries once, about 2 s later, with the same link', async (_name, first, waitMs) => {
    const api = fakeApi('level_knee', { s3: [first] })
    await reachPlace()
    await send()
    await advance(waitMs)
    expect(api.of('s3')).toHaveLength(1)

    await advance(2_000)
    expect(api.of('s3')).toHaveLength(2)
    expect(api.of('s3')[1]?.url).toBe(api.of('s3')[0]?.url)
    expect(api.of('upload')).toHaveLength(1)
    expect(heading().textContent).toBe(text('report.waitingTitle'))
  })

  it('a throttling 429 on POST /uploads retries once', async () => {
    const api = fakeApi('level_knee', { upload: [reply(429, { message: 'Too Many Requests' })] })
    await reachPlace()
    await send()
    expect(api.of('upload')).toHaveLength(1)

    await advance(2_000)
    expect(api.of('upload')).toHaveLength(2)
    expect(api.of('s3')).toHaveLength(1)
  })

  it.each(['device_limit', 'global_cap'] as const)(
    "a limit's 429 (%s) shows its own line and is never retried",
    async (code) => {
      const api = fakeApi(code)
      await reachPlace()
      await send()
      await advance(30_000)

      expect(api.of('upload')).toHaveLength(1)
      expect(api.of('s3')).toHaveLength(0)
      expect(screen.getByText(text(`report.limit.${code}`))).toBeTruthy()
      expect(screen.getByText(text('report.nothingUploaded'))).toBeTruthy()
      expect(queryButton('result.tryAgain')).toBeNull()
      expect(mainLink('nav.map').getAttribute('href')).toBe('#/map')
      expect(mainLink('nav.tested').getAttribute('href')).toBe('#/tested')
    },
  )

  it('an answer in the wrong shape is never retried', async () => {
    const api = fakeApi('level_knee', { upload: [reply(201, { unexpected: true })] })
    await reachPlace()
    await send()
    await advance(30_000)

    expect(api.of('upload')).toHaveLength(1)
    expect(screen.getByText(text('report.sendFailed'))).toBeTruthy()
    expect(screen.getByText(text('report.nothingUploaded'))).toBeTruthy()
    expect(button('report.newPhoto')).toBeTruthy()
  })

  it("after a failed retry, the upload problem's \"Try again\" reuses the photo and the link while it is 5 minutes old or less", async () => {
    const api = fakeApi('level_knee', { s3: [new TypeError('offline'), new TypeError('offline')] })
    await reachPlace()
    await send()
    await advance(2_000)

    expect(heading().textContent).toBe(text('report.notSent'))
    expect(screen.getByText(text('report.sendFailed'))).toBeTruthy()
    expect(api.of('s3')).toHaveLength(2)

    await advance(4 * 60_000)
    fireEvent.click(button('result.tryAgain'))
    await settle()
    expect(api.of('upload')).toHaveLength(1)
    expect(api.of('s3')).toHaveLength(3)
    expect(api.of('s3')[2]?.url).toBe(api.of('s3')[0]?.url)
    // A link still in its 5 minutes is used again without asking about the old report.
    expect(api.calls.findIndex((call) => call.kind === 'report')).toBeGreaterThan(
      api.calls.indexOf(api.of('s3')[2] as Call),
    )
    expect(getUserMedia).toHaveBeenCalledOnce()
    expect(heading().textContent).toBe(text('report.waitingTitle'))
  })

  it('past 5 minutes after a network failure, "Try again" asks about the old report once, and a pending one gets a new link', async () => {
    const api = fakeApi('level_knee', { s3: [new TypeError('offline'), new TypeError('offline')] })
    await reachPlace()
    await send()
    await advance(2_000)
    const oldUrl = api.of('s3')[0]?.url ?? ''
    const oldId = oldUrl.split('/').pop()
    // The link came at T0; it is now over 5 minutes old, and the photo is still under 15.
    await advance(5 * 60_000)

    fireEvent.click(button('result.tryAgain'))
    await settle()
    // The mock never got the photo, so the old report is still pending.
    const kinds = api.calls.map((call) => call.kind)
    expect(kinds.slice(3, 6)).toEqual(['report', 'upload', 's3'])
    expect(api.of('report')[0]?.url).toBe(`${API}/reports/${oldId}`)
    expect(api.of('upload')).toHaveLength(2)
    expect(api.uploadBody(1).capturedAt).toBe(new Date(T0).toISOString())
    expect(api.of('s3')).toHaveLength(3)
    expect(api.of('s3')[2]?.url).not.toBe(oldUrl)
  })

  it('an old report that already reads processing is waited on: no second POST /uploads, and the poll reads the old id', async () => {
    const api = fakeApi('level_knee', {
      s3: [new TypeError('offline'), new TypeError('offline')],
      report: [(url) => reply(200, { reportId: url.split('/').pop(), status: 'processing', mode: 'live', published: false })],
    })
    await reachPlace()
    await send()
    await advance(2_000)
    const oldId = api.of('s3')[0]?.url.split('/').pop()
    await advance(5 * 60_000 + 1)

    fireEvent.click(button('result.tryAgain'))
    await settle()
    expect(heading().textContent).toBe(text('report.waitingTitle'))
    await advance(POLL.fastMs * 2)
    expect(api.of('upload')).toHaveLength(1)
    expect(api.of('s3')).toHaveLength(2)
    expect(api.of('report').length).toBeGreaterThan(1)
    for (const call of api.of('report')) expect(call.url).toBe(`${API}/reports/${oldId}`)
  })

  it('two clicks on "Try again" while the old report is read make one read and one new link', async () => {
    const api = fakeApi('level_knee', { s3: [new TypeError('offline'), new TypeError('offline')] })
    await reachPlace()
    await send()
    await advance(2_000)
    await advance(5 * 60_000 + 1)
    const again = button('result.tryAgain')

    act(() => {
      again.click()
      again.click()
    })
    await settle()
    // One read of the old report, then one new link and its upload: a second read or link would show here.
    expect(api.calls.map((call) => call.kind).slice(3, 6)).toEqual(['report', 'upload', 's3'])
    expect(api.of('upload')).toHaveLength(2)
    expect(api.of('s3')).toHaveLength(3)
  })

  it('after an S3 4xx, "Try again" past 5 minutes asks for a new link without asking about the old report', async () => {
    const api = fakeApi('level_knee', { s3: [reply(403, {})] })
    await reachPlace()
    await send()
    await settle()
    expect(heading().textContent).toBe(text('report.notSent'))
    expect(api.of('s3')).toHaveLength(1)
    await advance(5 * 60_000 + 1)

    fireEvent.click(button('result.tryAgain'))
    await settle()
    expect(api.calls.map((call) => call.kind).slice(2, 4)).toEqual(['upload', 's3'])
    expect(api.of('upload')).toHaveLength(2)
  })

  it('a POST /uploads that fails twice on the network shows the upload problem, and "Try again" asks again', async () => {
    const api = fakeApi('level_knee', { upload: [new TypeError('offline'), new TypeError('offline')] })
    await reachPlace()
    await send()
    await advance(2_000)
    expect(api.of('upload')).toHaveLength(2)
    expect(screen.getByText(text('report.sendFailed'))).toBeTruthy()

    fireEvent.click(button('result.tryAgain'))
    await settle()
    expect(api.of('upload')).toHaveLength(3)
    expect(api.of('s3')).toHaveLength(1)
  })

  it('a failure while the browser says it is offline names the connection, and claims nothing about the photo', async () => {
    fakeApi('level_knee', { s3: [new TypeError('offline'), new TypeError('offline')] })
    await reachPlace()
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    await send()
    await advance(2_000)

    expect(screen.getByText(text('report.uploadFailed'))).toBeTruthy()
    expect(shows('report.sendFailed')).toBe(false)
    // The photo may have reached S3 before the connection dropped.
    expect(shows('report.nothingUploaded')).toBe(false)
    expect(button('result.tryAgain')).toBeTruthy()
  })

  it.each([
    ['a 500 on POST /uploads', { upload: [reply(500, { error: 'internal' })] }],
    ['an S3 403', { s3: [reply(403, {})] }],
  ])('%s, online, shows the neutral line with "Try again"', async (_name, script) => {
    fakeApi('level_knee', script)
    await reachPlace()
    await send()
    await settle()

    expect(screen.getByText(text('report.sendFailed'))).toBeTruthy()
    expect(shows('report.uploadFailed')).toBe(false)
    expect(button('result.tryAgain')).toBeTruthy()
  })

  it('the neutral line and the coarse-fix line read as the copy review set them', () => {
    expect(text('report.sendFailed')).toBe("Lusot couldn't send the photo. Try again.")
    expect(text('report.uploadFailed')).toBe('Check your connection, then try again.')
    expect(text('report.refused.gps_too_coarse')).toBe("Your phone's location wasn't precise enough to place the pin.")
  })

  it('two clicks on "Try again" in the same moment upload once', async () => {
    const api = fakeApi('level_knee', { s3: [new TypeError('offline'), new TypeError('offline')] })
    await reachPlace()
    await send()
    await advance(2_000)
    const again = button('result.tryAgain')

    act(() => {
      again.click()
      again.click()
    })
    await settle()
    expect(api.of('s3')).toHaveLength(3)
  })

  it('after 15 minutes, the upload problem asks for a new photo', async () => {
    fakeApi('level_knee', { s3: [new TypeError('offline'), new TypeError('offline')] })
    await reachPlace()
    await send()
    await advance(2_000)
    await advance(15 * 60_000)

    expect(queryButton('result.tryAgain')).toBeNull()
    expect(screen.getByText(text('report.tooOld'))).toBeTruthy()
    fireEvent.click(button('report.newPhoto'))
    await flush()
    expect(heading().textContent).toBe(text('camera.title'))
    expect(getUserMedia).toHaveBeenCalledTimes(2)
  })

  // The clock moves on while timers sleep (a phone in a pocket): each press checks the photo's age itself.
  it('a photo that turned 15 minutes old while timers slept is never sent, by "Send" or by "Try again"', async () => {
    const api = fakeApi('level_knee', { s3: [new TypeError('offline'), new TypeError('offline')] })
    await reachPlace()
    vi.setSystemTime(T0 + 15 * 60_000)
    await send()
    expect(api.of('upload')).toHaveLength(0)
    expect(screen.getByText(text('report.tooOld'))).toBeTruthy()

    cleanup()
    vi.setSystemTime(T0)
    await reachPlace()
    await send()
    await advance(2_000)
    vi.setSystemTime(T0 + 15 * 60_000)
    fireEvent.click(button('result.tryAgain'))
    await settle()
    expect(api.of('upload')).toHaveLength(1)
    expect(api.of('s3')).toHaveLength(2)
    expect(screen.getByText(text('report.tooOld'))).toBeTruthy()
  })

  it('a failed result\'s "Try again" starts the camera with no photo', async () => {
    fakeApi('failed_model_error')
    await reachPlace()
    await send()
    await advance(POLL.fastMs * 3)
    expect(screen.getByText(text('result.failed'))).toBeTruthy()

    fireEvent.click(button('result.tryAgain'))
    await flush()
    expect(heading().textContent).toBe(text('camera.title'))
    expect(getUserMedia).toHaveBeenCalledTimes(2)
  })
})

describe("the API's refusals", () => {
  it.each([
    ['capture_too_old', 'report.tooOld', 'report.newPhoto'],
    ['capture_in_future', 'report.refused.capture_in_future', 'report.newPhoto'],
    ['gps_too_coarse', 'report.refused.gps_too_coarse', 'location.retry'],
    ['nudge_too_far', 'report.refused.nudge_too_far', 'location.retry'],
  ] as const)('%s shows its line, with "Nothing was uploaded."', async (code, line, action) => {
    const api = fakeApi('level_knee', { upload: [reply(422, { error: code })] })
    await reachPlace()
    await send()
    await advance(30_000)

    expect(api.of('upload')).toHaveLength(1)
    expect(heading().textContent).toBe(text('report.notSent'))
    expect(screen.getByText(text(line))).toBeTruthy()
    expect(screen.getByText(text('report.nothingUploaded'))).toBeTruthy()
    expect(button(action)).toBeTruthy()
    expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
  })

  it('"Try the location again" after nudge_too_far keeps the photo and asks for a new fix, uploading nothing yet', async () => {
    const api = fakeApi('level_knee', { upload: [reply(422, { error: 'nudge_too_far' })] })
    await reachPlace()
    await send()

    fireEvent.click(button('location.retry'))
    await flush()
    expect(waitForFix).toHaveBeenCalledTimes(2)
    expect(api.of('upload')).toHaveLength(1)
    await act(async () => fixes[1]?.resolve(FIX))
    await send()
    expect(api.of('upload')).toHaveLength(2)
    expect(api.uploadBody(1).capturedAt).toBe(new Date(T0).toISOString())
  })

  it('a 503 uploads_paused shows the paused line and "Nothing was uploaded.", never "Processing failed"', async () => {
    const api = fakeApi('uploads_paused')
    await reachPlace()
    await send()
    await advance(30_000)

    expect(api.of('upload')).toHaveLength(1)
    expect(screen.getByText(text('result.paused'))).toBeTruthy()
    expect(screen.getByText(text('report.nothingUploaded'))).toBeTruthy()
    expect(shows('result.failed')).toBe(false)
    expect(mainLink('nav.map').getAttribute('href')).toBe('#/map')
    expect(mainLink('nav.tested').getAttribute('href')).toBe('#/tested')

    // Its "Try again" reuses the photo while it is under 15 minutes old.
    fireEvent.click(button('result.tryAgain'))
    await settle()
    expect(api.of('upload')).toHaveLength(2)
    expect(api.uploadBody(1).capturedAt).toBe(new Date(T0).toISOString())
    expect(getUserMedia).toHaveBeenCalledOnce()

    await advance(15 * 60_000)
    expect(queryButton('result.tryAgain')).toBeNull()
    expect(button('report.newPhoto')).toBeTruthy()
  })
})

describe('the location', () => {
  it('poor fix keeps the photo for a retry: the location line and "Try the location again", with no upload', async () => {
    const api = fakeApi()
    render(<Harness />)
    await openCamera()
    await shoot()
    await act(async () => fixes[0]?.reject(new PoorFix(80)))

    expect(screen.getByText(text('location.poor'))).toBeTruthy()
    expect(api.calls).toHaveLength(0)
    fireEvent.click(button('location.retry'))
    await flush()
    expect(waitForFix).toHaveBeenCalledTimes(2)
    expect(shows('report.locating')).toBe(true)

    await act(async () => fixes[1]?.resolve(FIX))
    await send()
    expect(api.of('upload')).toHaveLength(1)
    expect(api.uploadBody().capturedAt).toBe(new Date(T0).toISOString())
  })

  it('retry after 15 minutes asks for a new photo: "Try the location again" becomes "Take a new photo"', async () => {
    fakeApi()
    render(<Harness />)
    await openCamera()
    await shoot()
    await act(async () => fixes[0]?.reject(new PoorFix(80)))
    expect(button('location.retry')).toBeTruthy()

    await advance(15 * 60_000)
    expect(queryButton('location.retry')).toBeNull()
    fireEvent.click(button('report.newPhoto'))
    await flush()
    expect(heading().textContent).toBe(text('camera.title'))
    expect(waitForFix).toHaveBeenCalledOnce()
  })

  it('"Try the location again" on a photo that turned 15 minutes old while timers slept asks for a new photo', async () => {
    fakeApi()
    render(<Harness />)
    await openCamera()
    await shoot()
    await act(async () => fixes[0]?.reject(new PoorFix(80)))
    vi.setSystemTime(T0 + 15 * 60_000)

    fireEvent.click(button('location.retry'))
    await flush()
    expect(waitForFix).toHaveBeenCalledOnce()
    expect(button('report.newPhoto')).toBeTruthy()
  })

  it('a retried fix gives a fresh place step', async () => {
    fakeApi()
    await reachPlace()
    const before = heading()

    fireEvent.click(button('location.retry'))
    await flush()
    await act(async () => fixes[1]?.resolve({ ...FIX, lat: FIX.lat + 0.001 }))
    expect(heading().textContent).toBe(text('place.title'))
    expect(heading()).not.toBe(before)
  })

  it('a still under 1,600 px shows the small-still warning, and "Take a new photo" opens a fresh camera', async () => {
    fakeApi()
    await reachPlace({ width: 1280, height: 720 })

    const warning = screen.getByText(text('report.smallStill'))
    expect(heading().textContent).toBe(text('place.title'))
    expect(heading().compareDocumentPosition(warning) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(video()).toBeNull()
    fireEvent.click(button('report.newPhoto'))
    await flush()
    expect(getUserMedia).toHaveBeenCalledTimes(2)
    expect(button('camera.shutter')).toBeTruthy()
  })

  it('a full-size still shows no warning', async () => {
    fakeApi()
    await reachPlace()
    expect(shows('report.smallStill')).toBe(false)
  })
})

describe('the wait', () => {
  it('the wait survives a trip to the map', async () => {
    fakeApi()
    await reachPlace({ app: true })
    await send()
    expect(heading().textContent).toBe(text('report.waitingTitle'))

    go('#/map')
    await advance(POLL.fastMs * 3)
    go('#/report')
    await flush()

    expect(screen.getByText(KNEE_LINE)).toBeTruthy()
  })

  it('a wait that times out while the person is away is forgotten: no report id and no position stay', async () => {
    const api = fakeApi('pending_forever')
    await reachPlace()
    await send()
    const id = api.reportId()
    go('#/map')
    await advance(POLL.windowMs)

    expect(seen.state?.step).toBe('camera')
    expect(holds(seen.state, (leaf) => leaf === id)).toBe(false)
    expect(holds(seen.state, (leaf) => leaf === FIX.lat || leaf === FIX.lng)).toBe(false)
    go('#/report')
    await flush()
    expect(heading().textContent).toBe(text('camera.title'))
  })

  it('coming back to the app polls at once, with the same deadline', async () => {
    const api = fakeApi('pending_forever')
    await reachPlace()
    await send()
    await advance(30_000)
    const before = api.of('report').length

    setVisibility('hidden')
    await settle()
    expect(api.of('report')).toHaveLength(before)
    setVisibility('visible')
    await settle()
    expect(api.of('report')).toHaveLength(before + 1)

    const calls = vi.mocked(pollReport).mock.calls
    expect(calls).toHaveLength(2)
    const [first, again] = calls.map((call) => call[2])
    expect(Number.isFinite(first?.deadlineAt)).toBe(true)
    expect(again?.deadlineAt).toBe(first?.deadlineAt)
    expect(first?.deadlineAt).toBe(T0 + POLL.windowMs)
  })

  it('a PollTimeoutError shows "No result yet", and "Check again" polls the same report with no new upload', async () => {
    const api = fakeApi('pending_forever')
    await reachPlace()
    await send()
    const id = api.reportId()
    await advance(POLL.windowMs)

    expect(screen.getByText(text('result.noResult'))).toBeTruthy()
    const reads = api.of('report').length
    fireEvent.click(button('result.checkAgain'))
    await settle()

    expect(api.of('report')).toHaveLength(reads + 1)
    expect(api.of('report').at(-1)?.url).toBe(`${API}/reports/${id}`)
    expect(api.of('upload')).toHaveLength(1)
    expect(vi.mocked(pollReport).mock.calls.at(-1)).toEqual([
      API,
      id,
      expect.objectContaining({ startElapsedMs: 240_000 }),
    ])
    await advance(POLL.slowMs - 1)
    expect(api.of('report')).toHaveLength(reads + 1)
    await advance(1)
    expect(api.of('report')).toHaveLength(reads + 2)
  })
})

describe('what the flow keeps', () => {
  it('drops the photo once its upload succeeds, and the report id once the result screen closes', async () => {
    const api = fakeApi()
    await reachPlace()
    expect(holds(seen.state, (leaf) => leaf instanceof Blob)).toBe(true)

    await send()
    expect(holds(seen.state, (leaf) => leaf instanceof Blob)).toBe(false)
    await advance(POLL.fastMs * 3)
    expect(screen.getByText(KNEE_LINE)).toBeTruthy()
    const id = api.reportId()
    expect(holds(seen.state, (leaf) => leaf === id)).toBe(true)

    go('#/map')
    expect(holds(seen.state, (leaf) => leaf === id)).toBe(false)
    expect(holds(seen.state, (leaf) => typeof leaf === 'number' && (leaf === FIX.lat || leaf === FIX.lng))).toBe(false)
    expect(seen.state?.step).toBe('camera')
  })
})

describe('the own pin', () => {
  async function resultFor(scenario: Scenario, report?: (url: string) => Response) {
    const api = fakeApi(scenario, report === undefined ? {} : { report: [report] })
    await reachPlace()
    await send()
    await advance(POLL.fastMs * 3)
    return api
  }

  it('a done level result in live mode sets the own pin, from the sent position and the level fields', async () => {
    const api = await resultFor('level_knee')
    expect(seen.pin).toMatchObject({
      id: api.reportId(),
      own: true,
      mode: 'live',
      lat: FIX.lat,
      lng: FIX.lng,
      capturedAt: new Date(T0).toISOString(),
      level: 'knee',
      levelIsFloor: false,
    })
  })

  it("uses the fix's accuracy when the API sends none", async () => {
    await resultFor('level_knee', (url) =>
      reply(200, {
        reportId: url.split('/').pop(),
        status: 'done',
        mode: 'live',
        published: true,
        noFloodSeen: false,
        level: 'tire',
        landmark: 'rim_top',
        passability: 'NPATV',
        levelIsFloor: true,
        basis: { vehicles: 1, people: 0 },
      }),
    )
    expect(seen.pin).toMatchObject({ level: 'tire', levelIsFloor: true, gpsAccuracyM: FIX.accuracyM })
  })

  it.each([
    ['no flood seen', 'no_flood_seen'],
    ['a private result', 'level_private'],
  ] as const)('%s sets no own pin', async (_name, scenario) => {
    await resultFor(scenario)
    expect(seen.state?.step).toBe('result')
    expect(seen.pin).toBeUndefined()
  })

  it.each([
    ['a sample result', { mode: 'sample', published: false }],
    ['published: false', { mode: 'live', published: false }],
  ])('%s sets no own pin', async (_name, fields) => {
    await resultFor('level_knee', (url) =>
      reply(200, {
        reportId: url.split('/').pop(),
        status: 'done',
        noFloodSeen: false,
        level: 'knee',
        landmark: 'hub',
        passability: 'NPLV',
        levelIsFloor: false,
        basis: { vehicles: 1, people: 0 },
        ...fields,
      }),
    )
    expect(seen.state?.step).toBe('result')
    expect(seen.pin).toBeUndefined()
  })

  it('clears 2 minutes after it was set', async () => {
    await resultFor('level_knee')
    expect(seen.pin).toBeDefined()
    await advance(120_000 - POLL.fastMs * 3 - 1)
    expect(seen.pin).toBeDefined()
    await advance(POLL.fastMs * 3 + 1)
    expect(seen.pin).toBeUndefined()
  })

  it("clears at once when the map's pins hold its id, and not for other pins", async () => {
    await resultFor('level_knee')
    const pin = seen.pin as OwnPin
    const other: Pin = { ...pin, id: 'r_ffffffffffffffffffffffffffffffff' }

    act(() => seen.seenOnMap?.([other]))
    expect(seen.pin).toBeDefined()
    act(() => seen.seenOnMap?.([other, { ...pin }]))
    expect(seen.pin).toBeUndefined()
  })
})

// True when `test` holds for a value or anything inside it.
function holds(value: unknown, test: (leaf: unknown) => boolean): boolean {
  if (test(value)) return true
  if (value === null || typeof value !== 'object' || value instanceof Blob) return false
  return Object.values(value).some((child) => holds(child, test))
}
