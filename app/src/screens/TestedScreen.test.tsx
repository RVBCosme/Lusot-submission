import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { levelLine } from '../copy/wording'
import { LanguageProvider, makeT, type Lang } from '../i18n'
import { EN, type StringKey } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { getReport, getSamples, runSample } from '../lib/api'
import { GateProvider } from '../lib/consent'
import { POLL, pollReport } from '../lib/poll'
import { writeItem } from '../lib/storage'
import { fixture, ms6Fixture } from '../lib/__fixtures__/fixtures'
import { loadSummary, type Summary } from '../lib/summary'
import type { Scenario } from '../mock/fixtures'
import { createMockFetch } from '../mock/mockFetch'
import type { OwnPin } from '../report/flow'
import { ReportFlowProvider, useOwnPin } from '../report/ReportFlowProvider'
import { TestedScreen } from './TestedScreen'

// The app's fetch, swapped per test for Task 6's mock API, with a route or two scripted where a test needs it.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))
// The calls the page makes, watched, and answered by the real client behind them.
vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    getSamples: vi.fn(actual.getSamples),
    runSample: vi.fn(actual.runSample),
    getReport: vi.fn(actual.getReport),
  }
})
vi.mock('../lib/poll', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/poll')>()
  return { ...actual, pollReport: vi.fn(actual.pollReport) }
})

const API = 'https://api.example.test'
const T0 = Date.parse('2026-10-30T09:15:30.000Z')
const REPORT = 'r_0123456789abcdef0123456789abcdef'
const BANNED_WORDS = /safe|ligtas/i
const CROSSING = /you can cross|you can pass|go ahead|pu?wedeng dumaan|tumawid ka|lusutan mo/i
const NINE_LEVELS = /MMDA(['’]?s)? (9|nine) levels|(the )?(9|nine) MMDA levels/i
const REPORT_LINK = 'https://example.test/lusot/report'

const text = (key: StringKey) => EN[key].text
const en = makeT('en')
const KNEE_LINE = levelLine(en, 'knee', false).text

// ---- the harness ----

const seen: { pin?: OwnPin } = {}
function Probe() {
  const pin = useOwnPin()
  useEffect(() => {
    seen.pin = pin
  })
  return null
}

type Override = (method: string, path: string) => Response | Promise<Response> | undefined

// Task 6's mock API for a scenario; `override` answers a route itself when it returns a response.
function mockApi(scenario: Scenario = 'level_knee', override?: Override) {
  const base = createMockFetch({ scenario, now: () => Date.now() })
  net.fetch = (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input))
    const answer = override?.((init?.method ?? 'GET').toUpperCase(), url.pathname)
    return answer === undefined ? base(input, init) : Promise.resolve(answer)
  }
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

function renderPage({
  summary = null,
  apiUrl = API,
  reportUrl,
  lang = 'en',
}: { summary?: Summary | null; apiUrl?: string; reportUrl?: string; lang?: Lang } = {}) {
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  return render(
    <LanguageProvider>
      <ReportFlowProvider apiUrl={apiUrl}>
        <Probe />
        <main>
          <GateProvider>
            <TestedScreen apiUrl={apiUrl} summary={summary} reportUrl={reportUrl} />
          </GateProvider>
        </main>
      </ReportFlowProvider>
    </LanguageProvider>,
  )
}

const advance = async (ms: number) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}
const settle = () => advance(0)
const page = () => screen.getByRole('main')
const pageText = () => page().textContent ?? ''
const shows = (key: StringKey) => pageText().includes(text(key))
const runButtons = () => screen.queryAllByRole('button', { name: text('sample.run') }) as HTMLButtonElement[]
// A figure's row: its label, its value and its "indicative".
const row = (key: StringKey) => screen.getByText(text(key)).parentElement as HTMLElement
const adult = () => localStorage.setItem('lusot.consent', JSON.stringify({ adult: true }))
const sealed = () => loadSummary(fixture('sealed')) as Summary

async function openWithSamples(scenario: Scenario = 'level_knee', override?: Override, summary: Summary | null = null) {
  mockApi(scenario, override)
  renderPage({ summary })
  await settle()
}

async function runFirst() {
  fireEvent.click(runButtons()[0])
  await settle()
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] })
  vi.setSystemTime(T0)
  vi.mocked(getSamples).mockClear()
  vi.mocked(runSample).mockClear()
  vi.mocked(getReport).mockClear()
  vi.mocked(pollReport).mockClear()
  history.replaceState(null, '', '/#/tested')
  delete seen.pin
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  localStorage.clear()
  history.replaceState(null, '', '/')
  document.documentElement.removeAttribute('lang')
})

// ---- the figures ----

describe('the figures', () => {
  it('with no summary, the page explains how Lusot is tested, says the results appear after the sealed run on Nov 3, and shows no figure', () => {
    renderPage({ apiUrl: '' })
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(text('nav.tested'))
    expect(screen.getByRole('heading', { name: text('tested.how.title') })).toBeTruthy()
    for (const key of ['tested.how.labels', 'tested.how.sealed', 'tested.how.rules', 'tested.how.cars'] as const) {
      expect(shows(key), key).toBe(true)
    }
    expect(shows('tested.pending')).toBe(true)
    expect(pageText()).toContain('after the sealed run on Nov 3')
    expect(pageText()).not.toMatch(/\d+ of \d+/)
    expect(pageText()).not.toMatch(/\d in\b/)
    expect(pageText()).not.toContain(text('tested.indicative'))
  })

  it("with a synthetic run, MS6's committed fixture or the app's, the page shows no figure", () => {
    for (const pair of [ms6Fixture(), fixture('synthetic')]) {
      renderPage({ summary: loadSummary(pair), apiUrl: '' })
      expect(shows('tested.pending')).toBe(true)
      expect(pageText()).not.toMatch(/\d+ of \d+/)
      expect(pageText()).not.toMatch(/\d in\b/)
      cleanup()
    }
  })

  it('with the sealed fixture, it shows the three headline rates of shipped with their n, exact and within-one agreement, the word "indicative", and "how often Lusot agreed with the labels MMDA and the cities posted"', () => {
    renderPage({ summary: sealed(), apiUrl: '' })
    // `shipped` is geometry: its figures, not landmark's.
    expect(row('tested.figure.underestimation').textContent).toContain('10 of 80 (12.5%)')
    expect(row('tested.figure.passability').textContent).toContain('60 of 80 (75%)')
    expect(row('tested.figure.coverage').textContent).toContain('80 of 100 (80%)')
    expect(row('tested.figure.exact').textContent).toContain('40 of 80 (50%)')
    expect(row('tested.figure.withinOne').textContent).toContain('70 of 80 (87.5%)')
    expect(pageText()).not.toContain('20 of 70')
    // Every figure carries the word.
    for (const key of [
      'tested.figure.underestimation',
      'tested.figure.passability',
      'tested.figure.coverage',
      'tested.figure.exact',
      'tested.figure.withinOne',
    ] as const) {
      expect(row(key).textContent, key).toContain(text('tested.indicative'))
    }
    expect(pageText()).toContain('how often Lusot agreed with the labels MMDA and the cities posted')
    expect(shows('tested.shipped.geometry')).toBe(true)
    expect(pageText()).toContain('From the sealed run on Jan 1, 2000.')
    expect(shows('tested.pending')).toBe(false)
  })

  it('without exact and within-one, it links the report when REPORT_URL is set, and shows no link while it is unset', () => {
    const pair = fixture('sealed')
    const geometry = (pair.summary as { configurations: { geometry: Record<string, unknown> } }).configurations.geometry
    delete geometry.exact
    delete geometry.within_one
    const summary = loadSummary(pair) as Summary

    renderPage({ summary, apiUrl: '', reportUrl: REPORT_LINK })
    expect(screen.queryByText(text('tested.figure.exact'))).toBeNull()
    expect(screen.queryByText(text('tested.figure.withinOne'))).toBeNull()
    expect(row('tested.figure.underestimation').textContent).toContain('10 of 80 (12.5%)')
    const link = screen.getByRole('link', { name: text('tested.reportLink') })
    expect(link.getAttribute('href')).toBe(REPORT_LINK)
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    cleanup()

    // REPORT_URL stays undefined in this build: the page's own default gives no link.
    renderPage({ summary, apiUrl: '' })
    expect(screen.queryByRole('link', { name: text('tested.reportLink') })).toBeNull()
  })

  it('a rerun fixture wins over the first run', () => {
    const first = fixture('sealed')
    const rerun = fixture('rerun')
    renderPage({
      summary: loadSummary({ ...first, rerunSummary: rerun.summary, rerunRun: rerun.run }),
      apiUrl: '',
    })
    expect(pageText()).toContain('From the rerun on Jan 2, 2000')
    expect(row('tested.figure.underestimation').textContent).toContain('9 of 90 (10%)')
    expect(row('tested.figure.coverage').textContent).toContain('90 of 100 (90%)')
    expect(pageText()).not.toContain('10 of 80')
    expect(shows('tested.shipped.landmark')).toBe(true)
  })

  it("inches_shown: false says inches aren't shown, with the report link when REPORT_URL is set", () => {
    renderPage({ summary: sealed(), apiUrl: '', reportUrl: REPORT_LINK })
    expect(shows('tested.inches.notShown')).toBe(true)
    expect(shows('tested.inches.shown')).toBe(false)
    expect(screen.getByRole('link', { name: text('tested.reportLink') }).getAttribute('href')).toBe(REPORT_LINK)
    cleanup()

    const shown = fixture('sealed')
    ;(shown.summary as Record<string, unknown>).inches_shown = true
    renderPage({ summary: loadSummary(shown), apiUrl: '' })
    expect(shows('tested.inches.shown')).toBe(true)
    expect(shows('tested.inches.notShown')).toBe(false)
  })

  it("Set B's median shows whenever Set B's figures are present", () => {
    renderPage({ summary: sealed(), apiUrl: '' })
    expect(row('tested.setB.median').textContent).toContain('1.00 in, over 50 wheels')
    expect(row('tested.setB.median').textContent).toContain(text('tested.indicative'))
    expect(row('tested.setB.measured').textContent).toContain('50 of 60 (83.3%)')
    cleanup()

    // A folder with only Set B (MS6 §4.4): no headline rates, no inches line, and the median still shows.
    const onlyB = fixture('sealed')
    Object.assign(onlyB.summary as Record<string, unknown>, {
      configurations: null,
      shipped: null,
      geometry_stays: null,
      inches_shown: null,
    })
    renderPage({ summary: loadSummary(onlyB), apiUrl: '' })
    expect(row('tested.setB.median').textContent).toContain('1.00 in, over 50 wheels')
    expect(screen.queryByText(text('tested.figure.underestimation'))).toBeNull()
    expect(shows('tested.inches.notShown')).toBe(false)
    expect(shows('tested.pending')).toBe(false)
    cleanup()

    const noB = fixture('sealed')
    ;(noB.summary as Record<string, unknown>).set_b = null
    renderPage({ summary: loadSummary(noB), apiUrl: '' })
    expect(screen.queryByText(text('tested.setB.median'))).toBeNull()
    expect(row('tested.figure.underestimation').textContent).toContain('10 of 80 (12.5%)')
  })

  it('the page states Lusot\'s known limits (night, rain, blur, the face blur\'s misses) and holds "Not affiliated with MMDA."', () => {
    renderPage({ apiUrl: '' })
    expect(screen.getByRole('heading', { name: text('tested.limits.title') })).toBeTruthy()
    for (const key of ['tested.limits.night', 'tested.limits.rain', 'tested.limits.blur', 'tested.limits.faceBlur'] as const) {
      expect(shows(key), key).toBe(true)
    }
    expect(pageText()).toContain('Not affiliated with MMDA.')
  })

  it('the heading takes focus when the page opens', () => {
    renderPage({ apiUrl: '' })
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1 }))
  })
})

describe('words', () => {
  it('the words allow for the disclosed rerun and the pause: scored once with any rerun disclosed, and a live or saved reading', () => {
    renderPage({ apiUrl: '' })
    expect(pageText()).toContain('scored once')
    expect(pageText()).toContain('any rerun is disclosed with its reason')
    expect(pageText()).not.toContain('runs on them once')
    expect(pageText()).toContain('a live reading of the credited photo, or a saved one while new analyses are paused')
    expect(pageText()).not.toMatch(/fresh/i)
  })

  it('the page\'s text never contains "accuracy" or a banned word, in either language, before and after a sample runs', async () => {
    adult()
    for (const lang of ['en', 'fil'] as const) {
      for (const summary of [null, sealed()]) {
        mockApi('level_knee')
        renderPage({ summary, lang })
        await settle()
        const check = () => {
          const all = document.body.textContent ?? ''
          expect(all).not.toMatch(/accuracy/i)
          expect(all).not.toMatch(BANNED_WORDS)
          expect(all).not.toMatch(CROSSING)
          expect(all).not.toMatch(NINE_LEVELS)
        }
        check()
        const run = lang === 'en' ? EN['sample.run'].text : FIL['sample.run'].text
        fireEvent.click(screen.getAllByRole('button', { name: run })[0])
        await settle()
        await advance(POLL.fastMs)
        await advance(POLL.fastMs)
        expect(page().querySelector('[data-outcome="level"]')).not.toBeNull()
        check()
        cleanup()
        localStorage.removeItem('lusot.lang')
      }
    }
  })

  it('every Tested and sample line has a Taglish line, reviewed by Rene (Oct 31), with the same placeholders', () => {
    const keys = (Object.keys(EN) as StringKey[]).filter((key) => key.startsWith('tested.') || key.startsWith('sample.'))
    expect(keys.length).toBeGreaterThan(20)
    const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort()
    // Lines added on Nov 2 (C534, C640) wait for the tracker's review (M20): they still need a Taglish line.
    // Remove at M20 (Rene's review): then these keys join the reviewed check.
    const AWAITING_REVIEW: readonly StringKey[] = ['sample.limit.daily_cap', 'tested.try.title', 'tested.try.intro']
    const awaitingReview = (key: StringKey) => AWAITING_REVIEW.includes(key)
    for (const key of keys) {
      if (!awaitingReview(key)) {
        expect(EN[key].reviewed, key).toBe(true)
        expect(FIL[key].reviewed, key).toBe(true)
      }
      expect(FIL[key].text, key).not.toBe('')
      expect(placeholders(FIL[key].text), key).toEqual(placeholders(EN[key].text))
    }
  })
})

// ---- the samples ----

describe('the samples', () => {
  it("the sample list shows each sample's blurred photo, place, date, event and credit line", async () => {
    await openWithSamples()
    const samples = await vi.mocked(getSamples).mock.results[0].value
    const items = within(page()).getAllByRole('listitem').filter((item) => item.querySelector('img') !== null)
    expect(items).toHaveLength(3)
    const photos = screen.getAllByRole('img', { name: text('sample.photoAlt') })
    expect(photos.map((photo) => photo.getAttribute('src'))).toEqual(samples.map((s: { photoUrl: string }) => s.photoUrl))
    expect(pageText()).toContain('Photo from Sep 26, 2009, Marikina, Typhoon Ondoy')
    expect(pageText()).toContain('Photo: Example Contributor (mock), CC0 1.0')
    expect(pageText()).toContain('Photo from Oct 5, 2026, Manila')
    expect(within(items[0]).getByText(text('sample.edited'))).toBeTruthy()
    expect(runButtons()).toHaveLength(3)
    expect(shows('tested.samples.more')).toBe(false)
  })

  // The credit states how Lusot changed the photo, so the caption says it once, in the credit (the brief's step 15b).
  it('says the photo was blurred once: the line stays for a credit that does not say so, and goes for one that does', async () => {
    await openWithSamples()
    const items = within(page()).getAllByRole('listitem').filter((item) => item.querySelector('img') !== null)
    expect(items).toHaveLength(3)
    expect(within(items[0]).getAllByText(text('sample.edited'))).toHaveLength(1)
    for (const item of [items[1], items[2]]) {
      expect(item.textContent).toMatch(/blurred by Lusot/)
      expect(item.textContent).not.toContain(text('sample.edited'))
    }
  })

  // I2: the credit states the blur, never the outlines a run draws, so the run's card says it drew them, and the
  // blurred line stays left out, as in the list.
  it("a run of a sample whose credit says it was blurred says only that Lusot drew its outlines", async () => {
    adult()
    await openWithSamples('level_knee')
    fireEvent.click(runButtons()[1])
    await settle()
    await advance(POLL.fastMs)
    await advance(POLL.fastMs)
    const card = page().querySelector('article[data-outcome="level"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(card.textContent).toMatch(/blurred by Lusot/)
    expect(card.textContent).not.toContain(text('sample.edited'))
    expect(within(card).getByText(text('sample.outlines'))).toBeTruthy()
  })

  it('leaves out a place or event of "unknown", and shows a real one as written', async () => {
    const listed = (await (await createMockFetch({ now: () => Date.now() })(`${API}/samples`)).json()) as {
      samples: Record<string, unknown>[]
    }
    const samples = [
      { ...listed.samples[0], place: 'unknown', event: 'Typhoon Ondoy' },
      { ...listed.samples[1], place: 'Unknown ', event: 'UNKNOWN' },
      { ...listed.samples[2], place: 'Baliuag, Bulacan', event: 'Typhoon Ondoy' },
    ]
    mockApi('level_knee', (method, path) => (method === 'GET' && path === '/samples' ? json(200, { samples }) : undefined))
    renderPage()
    await settle()
    expect(pageText()).toContain('Photo from Sep 26, 2009, Typhoon Ondoy')
    expect(pageText()).toContain('Photo from Aug 7, 2012')
    expect(pageText()).toContain('Photo from Oct 5, 2026, Baliuag, Bulacan, Typhoon Ondoy')
    expect(pageText()).not.toMatch(/unknown/i)
  })

  it('"Run this sample" passes the 18+ gate and calls runSample once, then polls and shows the result card with the Sample badge', async () => {
    await openWithSamples()
    fireEvent.click(runButtons()[0])
    await settle()
    expect(screen.getByRole('heading', { name: text('consent.adultTitle') })).toBeTruthy()
    expect(runSample).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: text('consent.continue') }))
    await settle()
    expect(runSample).toHaveBeenCalledOnce()
    expect(vi.mocked(runSample).mock.calls[0].slice(0, 2)).toEqual([API, 'sample-01'])
    expect(shows('sample.reading')).toBe(true)
    // Its own poll, with Task 5's absolute deadline 600 s after the run started.
    expect(pollReport).toHaveBeenCalledOnce()
    const [, reportId, options] = vi.mocked(pollReport).mock.calls[0]
    expect(reportId).toMatch(/^r_[0-9a-f]{32}$/)
    expect(options?.deadlineAt).toBe(T0 + POLL.windowMs)
    expect(options?.startElapsedMs ?? 0).toBe(0)
    expect(options?.signal).toBeInstanceOf(AbortSignal)

    await advance(POLL.fastMs)
    await advance(POLL.fastMs)
    const card = page().querySelector('article[data-outcome="level"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(within(card).getByText(text('badge.sample'))).toBeTruthy()
    expect(card.textContent).toContain(KNEE_LINE)
    expect(card.textContent).toContain(text('sample.liveReading'))
    expect(card.textContent).toContain('Photo from Sep 26, 2009, Marikina, Typhoon Ondoy')
    expect(runSample).toHaveBeenCalledOnce()
    // The sample that ran has no button of its own any more; the others are free again.
    expect(runButtons()).toHaveLength(2)
    expect(runButtons().every((button) => !button.disabled)).toBe(true)
  })

  it('run twice starts one sample', async () => {
    adult()
    await openWithSamples()
    const [first] = runButtons()
    // Two taps in one tick, before React draws the button as busy: the once-only guard holds.
    act(() => {
      first.click()
      first.click()
    })
    await settle()
    expect(runSample).toHaveBeenCalledOnce()
    // While it runs, no other sample can start.
    expect(runButtons().every((button) => button.disabled)).toBe(true)
    fireEvent.click(runButtons()[0])
    await settle()
    expect(runSample).toHaveBeenCalledOnce()
    cleanup()

    // Through the gate: two taps open it once, and "Continue" starts one run.
    localStorage.clear()
    vi.mocked(runSample).mockClear()
    await openWithSamples()
    act(() => {
      runButtons()[0].click()
      runButtons()[0].click()
    })
    await settle()
    fireEvent.click(screen.getByRole('checkbox'))
    const proceed = screen.getByRole('button', { name: text('consent.continue') })
    act(() => {
      proceed.click()
      proceed.click()
    })
    await settle()
    expect(runSample).toHaveBeenCalledOnce()
  })

  it('a short samples list still reads well', async () => {
    adult()
    const check = async (scenario: Scenario, override?: Override) => {
      await openWithSamples(scenario, override, sealed())
      // The figures and the other sections stay.
      expect(row('tested.figure.underestimation').textContent).toContain('10 of 80 (12.5%)')
      expect(screen.getByRole('heading', { name: text('tested.limits.title') })).toBeTruthy()
      expect(screen.getByRole('heading', { name: text('tested.samples.title') })).toBeTruthy()
      expect(shows('tested.samples.more')).toBe(true)
      expect(screen.queryByRole('alert')).toBeNull()
      const samples = screen.getByRole('heading', { name: text('tested.samples.title') }).closest('section') as HTMLElement
      expect(samples.textContent).not.toMatch(/error|failed|couldn't/i)
      const count = runButtons().length
      cleanup()
      return count
    }
    // "Short" is fewer than 3 samples.
    expect(await check('samples_one')).toBe(1)
    expect(await check('samples_two')).toBe(2)
    expect(await check('samples_none')).toBe(0)
    expect(await check('level_knee', (_, path) => (path === '/samples' ? json(500, {}) : undefined))).toBe(0)
    expect(await check('level_knee', (_, path) => (path === '/samples' ? json(200, { samples: 'no' }) : undefined))).toBe(0)
  })

  it('a sample run that refuses shows the result card\'s refused outcome with the sample frame, never an error', async () => {
    adult()
    await openWithSamples('refused_no_usable_reference')
    await runFirst()
    await advance(POLL.fastMs)
    await advance(POLL.fastMs)
    const card = page().querySelector('article[data-outcome="cant-tell"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(card.textContent).toContain(text('verdict.none'))
    expect(card.textContent).toContain(text('reason.no_usable_reference'))
    expect(card.textContent).toContain(text('refusal.sample.someoneWouldSee'))
    expect(card.textContent).toContain(text('refusal.d19'))
    expect(card.querySelector('img')).not.toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(pageText()).not.toContain(text('result.failed'))
  })

  it('a sample result never sets the own pin', async () => {
    adult()
    await openWithSamples('level_knee')
    await runFirst()
    await advance(POLL.fastMs)
    await advance(POLL.fastMs)
    expect(page().querySelector('article[data-outcome="level"]')).not.toBeNull()
    await advance(POLL.fastMs)
    expect(seen.pin).toBeUndefined()
  })

  it('a 503 uploads_paused from runSample shows the paused line with a link to the map, and no "Nothing was uploaded." or "Processing failed"', async () => {
    adult()
    await openWithSamples('uploads_paused')
    await runFirst()
    expect(runSample).toHaveBeenCalledOnce()
    expect(shows('result.paused')).toBe(true)
    expect(screen.getByRole('link', { name: text('nav.map') }).getAttribute('href')).toBe('#/map')
    // The paused line leaves out the screen it is on.
    expect(screen.queryByRole('link', { name: text('nav.tested') })).toBeNull()
    expect(shows('report.nothingUploaded')).toBe(false)
    expect(shows('result.failed')).toBe(false)
    expect(pollReport).not.toHaveBeenCalled()
    await advance(5000)
    expect(runSample).toHaveBeenCalledOnce()
  })

  it('after a 503 uploads_paused the sample keeps its button, and a second tap runs it again exactly once', async () => {
    adult()
    await openWithSamples('uploads_paused')
    await runFirst()
    expect(runSample).toHaveBeenCalledOnce()
    // Nothing was started, and the switch can come back off (C638): the paused line, then the sample's own button.
    const item = screen.getByText(text('result.paused')).closest('li') as HTMLElement
    const again = within(item).getByRole('button', { name: text('sample.run') }) as HTMLButtonElement
    expect(again.disabled).toBe(false)
    expect(runButtons()).toHaveLength(3)
    const paused = within(item).getByText(text('result.paused'))
    expect(paused.compareDocumentPosition(again) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    // Two taps in one tick: the once-only guard still holds, so one more run.
    act(() => {
      again.click()
      again.click()
    })
    await settle()
    expect(runSample).toHaveBeenCalledTimes(2)
    expect(shows('result.paused')).toBe(true)
    await advance(5000)
    expect(runSample).toHaveBeenCalledTimes(2)
  })

  it("a sample that ends failed/model_calls_paused shows Task 8's paused card", async () => {
    adult()
    await openWithSamples('level_knee', (method, path) => {
      if (method === 'POST' && path.startsWith('/samples/')) return json(201, { reportId: REPORT })
      if (path === `/reports/${REPORT}`) {
        return json(200, { reportId: REPORT, status: 'failed', refusalReason: 'model_calls_paused', mode: 'sample', published: false })
      }
      return undefined
    })
    await runFirst()
    await settle()
    const card = page().querySelector('article[data-outcome="paused"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(card.textContent).toContain(text('result.paused'))
    expect(within(card).getByRole('link', { name: text('nav.map') })).toBeTruthy()
    expect(within(card).queryByRole('link', { name: text('nav.tested') })).toBeNull()
    expect(pageText()).not.toContain(text('result.failed'))
    expect(within(card).queryByRole('button', { name: text('result.tryAgain') })).toBeNull()
    // A pause is not a failure, so it doesn't bring back the sample's button (M4 leaves this case as it was).
    expect(within(card.closest('li') as HTMLElement).queryByRole('button', { name: text('sample.run') })).toBeNull()
  })

  // M4: the server reported the failure, so a new run is a new report that pays once. The card's own words ask for
  // another try, so the sample offers its button again.
  it('a sample run that ends failed offers "Run this sample" again, and a press starts exactly one new run', async () => {
    adult()
    await openWithSamples('failed_model_error')
    await runFirst()
    await advance(POLL.fastMs)
    await advance(POLL.fastMs)
    const card = page().querySelector('article[data-outcome="failed"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(card.textContent).toContain(text('result.failed'))
    expect(runSample).toHaveBeenCalledOnce()
    const item = card.closest('li') as HTMLElement
    const again = within(item).getByRole('button', { name: text('sample.run') }) as HTMLButtonElement
    expect(again.disabled).toBe(false)
    expect(card.compareDocumentPosition(again) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(runButtons()).toHaveLength(3)

    // Two taps in one tick: the once-only guard holds, so one new run, with its own poll.
    act(() => {
      again.click()
      again.click()
    })
    await settle()
    expect(runSample).toHaveBeenCalledTimes(2)
    expect(vi.mocked(runSample).mock.calls[1].slice(0, 2)).toEqual([API, 'sample-01'])
    expect(pollReport).toHaveBeenCalledTimes(2)
    expect(shows('sample.reading')).toBe(true)
    await advance(10_000)
    expect(runSample).toHaveBeenCalledTimes(2)
  })

  it("a failed sample's button waits while another sample runs (one run at a time), and its press passes the 18+ check", async () => {
    adult()
    await openWithSamples('failed_model_error')
    await runFirst()
    await advance(POLL.fastMs)
    await advance(POLL.fastMs)
    const item = (page().querySelector('article[data-outcome="failed"]') as HTMLElement).closest('li') as HTMLElement
    const again = () => within(item).getByRole('button', { name: text('sample.run') }) as HTMLButtonElement

    // Another sample starts: the failed one's button is disabled until that run ends.
    fireEvent.click(runButtons()[1])
    await settle()
    expect(runSample).toHaveBeenCalledTimes(2)
    expect(again().disabled).toBe(true)
    fireEvent.click(again())
    await settle()
    expect(runSample).toHaveBeenCalledTimes(2)
    await advance(POLL.fastMs)
    await advance(POLL.fastMs)
    expect(again().disabled).toBe(false)

    // With the 18+ answer gone, the press asks again before any run.
    localStorage.removeItem('lusot.consent')
    fireEvent.click(again())
    await settle()
    expect(screen.getByRole('heading', { name: text('consent.adultTitle') })).toBeTruthy()
    expect(runSample).toHaveBeenCalledTimes(2)
  })

  it('a sample run that read a level, no flood or a refusal offers no second run of that sample', async () => {
    adult()
    const cases: [Scenario, string][] = [
      ['level_knee', 'level'],
      ['no_flood_seen', 'no-flood'],
      ['refused_no_usable_reference', 'cant-tell'],
    ]
    for (const [scenario, outcome] of cases) {
      vi.mocked(runSample).mockClear()
      await openWithSamples(scenario)
      await runFirst()
      await advance(POLL.fastMs)
      await advance(POLL.fastMs)
      const card = page().querySelector(`article[data-outcome="${outcome}"]`) as HTMLElement
      expect(card, scenario).not.toBeNull()
      const item = card.closest('li') as HTMLElement
      expect(within(item).queryByRole('button', { name: text('sample.run') }), scenario).toBeNull()
      expect(runButtons(), scenario).toHaveLength(2)
      expect(runSample, scenario).toHaveBeenCalledOnce()
      cleanup()
    }
  })

  it('no API address: the samples are off with a plain line, and the figures still show', async () => {
    renderPage({ summary: sealed(), apiUrl: '' })
    await settle()
    expect(shows('tested.samples.noApi')).toBe(true)
    expect(runButtons()).toHaveLength(0)
    expect(getSamples).not.toHaveBeenCalled()
    expect(row('tested.figure.underestimation').textContent).toContain('10 of 80 (12.5%)')
  })

  it('a poll that runs out shows "No result yet", and "Check again" polls the same report without running the sample again', async () => {
    adult()
    await openWithSamples('pending_forever')
    await runFirst()
    const firstId = vi.mocked(pollReport).mock.calls[0][1]
    await advance(POLL.windowMs)
    const card = page().querySelector('article[data-outcome="no-result"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(card.textContent).toContain(text('result.noResult'))
    expect(card.querySelector('img')).not.toBeNull()
    expect(runButtons()).toHaveLength(2)

    const checkedAt = Date.now()
    fireEvent.click(within(card).getByRole('button', { name: text('result.checkAgain') }))
    await settle()
    expect(pollReport).toHaveBeenCalledTimes(2)
    const [, againId, options] = vi.mocked(pollReport).mock.calls[1]
    expect(againId).toBe(firstId)
    expect(options?.startElapsedMs).toBe(POLL.midForMs)
    expect(options?.deadlineAt).toBe(checkedAt + POLL.windowMs)
    expect(shows('sample.reading')).toBe(true)
    await advance(POLL.windowMs)
    expect(page().querySelector('article[data-outcome="no-result"]')).not.toBeNull()
    expect(runSample).toHaveBeenCalledOnce()
  })

  it('a runSample that gets no answer says the run may still finish, and offers no second run of that sample', async () => {
    adult()
    const cases: Override[] = [
      // No answer within 15 s.
      (method, path) => (method === 'POST' && path.startsWith('/samples/') ? new Promise<Response>(() => {}) : undefined),
      // A lost connection.
      (method, path) =>
        method === 'POST' && path.startsWith('/samples/') ? Promise.reject(new TypeError('Failed to fetch')) : undefined,
      // An answer in the wrong shape, after the server acted.
      (method, path) => (method === 'POST' && path.startsWith('/samples/') ? json(201, {}) : undefined),
      // A server error, which can come after a run started.
      (method, path) => (method === 'POST' && path.startsWith('/samples/') ? json(502, { message: 'Bad Gateway' }) : undefined),
    ]
    for (const override of cases) {
      vi.mocked(runSample).mockClear()
      await openWithSamples('level_knee', override)
      await runFirst()
      await advance(15_000)
      expect(shows('sample.unanswered')).toBe(true)
      expect(pageText()).toContain('may still finish')
      expect(runButtons()).toHaveLength(2)
      expect(runButtons().every((button) => !button.disabled)).toBe(true)
      await advance(20_000)
      expect(runSample).toHaveBeenCalledOnce()
      expect(pollReport).not.toHaveBeenCalled()
      cleanup()
    }
  })

  it('a limit 429, a 404 and other refusals are shown and never retried', async () => {
    adult()
    const cases: [Scenario, Override | undefined, StringKey, number][] = [
      ['device_limit', undefined, 'sample.limit.device_limit', 2],
      ['global_cap', undefined, 'sample.limit.global_cap', 2],
      ['level_knee', (method, path) => (method === 'POST' && path.startsWith('/samples/') ? json(404, { error: 'not_found' }) : undefined), 'sample.gone', 2],
      // Nothing ran: the run can be tried again by hand, never by the app.
      ['level_knee', (method, path) => (method === 'POST' && path.startsWith('/samples/') ? json(400, { error: 'bad_request' }) : undefined), 'sample.failed', 3],
      ['level_knee', (method, path) => (method === 'POST' && path.startsWith('/samples/') ? json(429, { message: 'Too Many Requests' }) : undefined), 'sample.failed', 3],
    ]
    for (const [scenario, override, line, buttons] of cases) {
      vi.mocked(runSample).mockClear()
      await openWithSamples(scenario, override)
      await runFirst()
      expect(shows(line), line).toBe(true)
      expect(runButtons(), line).toHaveLength(buttons)
      await advance(10_000)
      expect(runSample, line).toHaveBeenCalledOnce()
      expect(pollReport).not.toHaveBeenCalled()
      cleanup()
    }
  })

  it('a sample refused by daily_cap shows sample.limit.daily_cap and keeps Run this sample hidden', async () => {
    adult()
    // MS4's C534: a day's cap on paid sample runs. Nothing ran, and the app never retries it.
    await openWithSamples('level_knee', (method, path) =>
      method === 'POST' && path.startsWith('/samples/') ? json(429, { error: 'daily_cap' }) : undefined,
    )
    await runFirst()
    expect(shows('sample.limit.daily_cap')).toBe(true)
    expect(runButtons()).toHaveLength(2)
    await advance(10_000)
    expect(runSample).toHaveBeenCalledOnce()
    expect(pollReport).not.toHaveBeenCalled()
  })

  it('the poll stops when the page closes', async () => {
    adult()
    await openWithSamples('pending_forever')
    await runFirst()
    await advance(POLL.fastMs)
    const signal = vi.mocked(pollReport).mock.calls[0][2]?.signal
    cleanup()
    expect(signal?.aborted).toBe(true)
    const reads = vi.mocked(getReport).mock.calls.length
    await advance(30_000)
    expect(vi.mocked(getReport).mock.calls.length).toBe(reads)
  })

  it("the run's status takes focus when the button goes", async () => {
    adult()
    await openWithSamples('pending_forever')
    runButtons()[0].focus()
    await runFirst()
    const status = screen.getByText(text('sample.reading'))
    expect(document.activeElement?.contains(status)).toBe(true)
  })

  it('an expired photo link asks for fresh links, at most once a minute', async () => {
    await openWithSamples()
    expect(getSamples).toHaveBeenCalledOnce()
    const photo = () => screen.getAllByRole('img', { name: text('sample.photoAlt') })[0]
    await advance(60_000)
    fireEvent.error(photo())
    await settle()
    expect(getSamples).toHaveBeenCalledTimes(2)
    fireEvent.error(photo())
    await settle()
    expect(getSamples).toHaveBeenCalledTimes(2)
    await advance(60_000)
    fireEvent.error(photo())
    await settle()
    expect(getSamples).toHaveBeenCalledTimes(3)
    expect(runButtons()).toHaveLength(3)
  })
})

// ---- a photo the person chooses (C534, C640) ----

describe('your own photo', () => {
  it('the Tested page shows the Try your own photo section after the samples', async () => {
    await openWithSamples()
    const headings = within(page()).getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)

    expect(headings.indexOf(text('tested.try.title'))).toBe(headings.indexOf(text('tested.samples.title')) + 1)
    const section = screen.getByRole('region', { name: text('tested.try.title') })
    expect(section.textContent).toContain(text('tested.try.intro'))
    expect(within(section).getByRole('button', { name: text('try.choose') })).toBeTruthy()
    const samples = screen.getByRole('region', { name: text('tested.samples.title') })
    expect(samples.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

// ---- a saved result while analysis is paused (Step 6) ----

describe('a saved result while analysis is paused', () => {
  const SAVED_AT = '2026-10-29T14:20:00Z'
  const savedRun = (result: unknown, savedAt: unknown = SAVED_AT): Override => (method, path) =>
    method === 'POST' && path.startsWith('/samples/') ? json(200, { saved: true, savedAt, result }) : undefined

  it("a sample run answering 200 { saved: true, savedAt, result } shows the paused line, then the saved result through the result card, with no poll", async () => {
    adult()
    // MS4's C527 while model calls are paused: each sample's seeding run, saved and dated.
    await openWithSamples('failed_model_calls_paused')
    await runFirst()
    expect(runSample).toHaveBeenCalledOnce()
    expect(pollReport).not.toHaveBeenCalled()
    expect(getReport).not.toHaveBeenCalled()

    const card = page().querySelector('article[data-outcome="level"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(within(card).getByText(text('badge.sample'))).toBeTruthy()
    // The paused line comes first, then the saved reading.
    const paused = within(card).getByText(text('result.paused'))
    const level = within(card).getByText(KNEE_LINE)
    expect(paused.compareDocumentPosition(level) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(card.textContent).toContain('Saved result from Oct 29, 2026')
    expect(card.textContent).toContain(text('sample.savedReading'))
    expect(card.textContent).not.toContain(text('sample.liveReading'))
    // The paused line links to the map, and leaves out the Tested page it is on.
    expect(within(card).getByRole('link', { name: text('nav.map') })).toBeTruthy()
    expect(within(card).queryByRole('link', { name: text('nav.tested') })).toBeNull()
    // No basis, overlay or inches for a saved answer (amendment 10), and no outlines claimed.
    expect(card.textContent).not.toContain('Estimated')
    expect(card.textContent).not.toContain(text('result.levelFrom.geometry'))
    expect(card.textContent).not.toMatch(/From \d+ reference object/)
    expect(card.textContent).not.toContain(text('sample.outlines'))
    expect(card.querySelector('img')).not.toBeNull()
    expect(pageText()).not.toContain(text('result.failed'))
    // No second run of it on the spot; the others still run.
    expect(runButtons()).toHaveLength(2)
    expect(runButtons().every((button) => !button.disabled)).toBe(true)

    // The next sample's saved answer is "no flood seen".
    await runFirst()
    const dry = page().querySelector('article[data-outcome="no-flood"]') as HTMLElement
    expect(dry).not.toBeNull()
    expect(dry.textContent).toContain(text('result.noFlood'))
    expect(dry.textContent).toContain(text('result.paused'))
    expect(dry.textContent).toContain(text('sample.savedReading'))
    expect(runSample).toHaveBeenCalledTimes(2)
    expect(pollReport).not.toHaveBeenCalled()
  })

  it("a saved refused result gets C637's sample frame", async () => {
    adult()
    await openWithSamples('level_knee', savedRun({ status: 'refused', refusalReason: 'no_usable_reference' }))
    await runFirst()
    const card = page().querySelector('article[data-outcome="cant-tell"]') as HTMLElement
    expect(card).not.toBeNull()
    expect(card.textContent).toContain(text('result.paused'))
    expect(card.textContent).toContain('Saved result from Oct 29, 2026')
    expect(card.textContent).toContain(text('verdict.none'))
    expect(card.textContent).toContain(text('reason.no_usable_reference'))
    expect(card.textContent).toContain(text('refusal.sample.someoneWouldSee'))
    expect(card.textContent).toContain(text('refusal.d19'))
    expect(card.textContent).toContain(text('sample.savedReading'))
    expect(screen.queryByRole('alert')).toBeNull()
    expect(pollReport).not.toHaveBeenCalled()
  })

  it('a saved answer in the wrong shape shows a plain line, never a card, and nothing is retried', async () => {
    adult()
    const cases: Override[] = [
      // No date.
      (method, path) =>
        method === 'POST' && path.startsWith('/samples/')
          ? json(200, { saved: true, result: { status: 'done', noFloodSeen: true } })
          : undefined,
      savedRun({ status: 'done', noFloodSeen: true }, 'not a date'),
      savedRun({ status: 'pending' }),
      savedRun({ status: 'done' }), // neither a level nor "no flood seen"
      savedRun({ status: 'done', noFloodSeen: false, level: 'ankle' }), // not one of the 9 levels
      savedRun(undefined),
    ]
    for (const override of cases) {
      vi.mocked(runSample).mockClear()
      await openWithSamples('level_knee', override)
      await runFirst()
      expect(page().querySelector('article')).toBeNull()
      expect(shows('sample.failed')).toBe(true)
      // A saved answer means nothing ran, so the sample can be tried again by hand.
      expect(runButtons()).toHaveLength(3)
      await advance(10_000)
      expect(runSample).toHaveBeenCalledOnce()
      expect(pollReport).not.toHaveBeenCalled()
      cleanup()
    }
  })
})
