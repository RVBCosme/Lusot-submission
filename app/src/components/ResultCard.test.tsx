import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LEVELS, PASSABILITY, REFUSED_REASONS, type Level } from '../copy/levels'
import { LanguageProvider, unreviewedKeys } from '../i18n'
import { EN } from '../i18n/en'
import { FIL } from '../i18n/fil'
import {
  getPins,
  getReport,
  getSamples,
  postToS3,
  requestUpload,
  runSample,
  type Pin,
  type ReportResult,
  type SavedSample,
} from '../lib/api'
import { pollReport } from '../lib/poll'
import { writeItem } from '../lib/storage'
import { createMockFetch } from '../mock/mockFetch'
import { levelLayers, scenarioNames, type Scenario } from '../mock/fixtures'
import { prefersReducedMotion } from '../test/motion'
import { PausedNotice, ResultCard } from './ResultCard'

// The overlay fetches the layers file through the app's fetch. A test points it at the mock that made the report,
// whose layers file belongs to that report, and until then it has no network.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))

const API = 'https://mock.invalid'
const DEVICE = '0f8e4a52-3c1d-4b7a-9e26-5d0c8b1f7a43'
const NOW = Date.parse('2026-10-30T10:20:00Z')
const JPEG = new Blob(['jpeg bytes'], { type: 'image/jpeg' })
const REQ = {
  lat: 14.6095,
  lng: 120.9894,
  gpsAccuracyM: 12,
  capturedAt: new Date(NOW - 60_000).toISOString(),
  nudgeM: 18,
  consentVersion: '3f9a1c07',
}

const D19 = EN['refusal.d19'].text
// A credit that doesn't say the photo was blurred, so the card keeps its own blurred and outlines lines. The mock's demo
// pin credit does say it, which leaves the card's lines out (step 15b).
const PLAIN_CREDIT = 'Photo: Example Contributor (mock), CC0 1.0'
const BANNED_WORDS = /safe|ligtas/i
const CROSSING = /you can cross|you can pass|go ahead|pu?wedeng dumaan|tumawid ka|lusutan mo/i
const NINE_LEVELS = /MMDA(['’]?s)? (9|nine) levels|(the )?(9|nine) MMDA levels/i
const WHOLE_ROAD = /\b(roads?|routes?|streets?|highways?|lanes?)\b|kalsada|\bdaan\b|\bruta\b/i
const APPROACH =
  /\b(approach|walk|wade|wading|step|go to|drive|closer|enter)\b|lumapit|lumusong|pumunta|maglakad|magmaneho|pumasok/i

beforeEach(() => {
  localStorage.clear()
  net.fetch = () => Promise.reject(new TypeError('No network in the test environment'))
  // The card's overlay is checked in its final frame (C615's draw-in is OverlayView.test.tsx's).
  prefersReducedMotion(true)
})

afterEach(async () => {
  // A layers answer still on its way lands inside act, and then the card goes.
  await act(async () => {})
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('lang')
})

// A clock the mock and the poll share: sleeping moves it, so a wait takes no time.
function clock() {
  let t = NOW
  return {
    now: () => t,
    sleep: async (ms: number) => {
      t += ms
    },
  }
}

function mockWith(scenario?: Scenario) {
  const c = clock()
  const fetchFn = createMockFetch({ scenario, now: c.now })
  net.fetch = fetchFn
  return { fetchFn, c }
}

// The whole trip a photo takes, as the app makes it: the upload link, the photo, then the poll to a final status.
async function takePhoto(scenario?: Scenario): Promise<ReportResult> {
  const { fetchFn, c } = mockWith(scenario)
  const { reportId, upload } = await requestUpload(API, REQ, DEVICE, fetchFn)
  await postToS3(upload, JPEG, fetchFn)
  return pollReport(API, reportId, { fetchFn, sleep: c.sleep, now: c.now })
}

type Props = Partial<ComponentProps<typeof ResultCard>> & { result: ReportResult | Pin }

function renderCard(props: Props, lang: 'en' | 'fil' = 'en') {
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  return render(
    <LanguageProvider>
      <ResultCard source="own" {...props} />
    </LanguageProvider>,
  )
}

// 25 minutes after the photo was taken.
const laterBy25 = (result: ReportResult) => new Date(Date.parse(result.capturedAt as string) + 25 * 60_000)

const text = () => document.body.textContent ?? ''

// The elements that say `line` outside the Details disclosure.
const outsideDetails = (line: string) => screen.getAllByText(line).filter((element) => element.closest('details') === null)

// A pin with every field a live level result carries, for the levels the mock doesn't read.
function pinAt(level: Level, extra: Partial<Pin> = {}): Pin {
  return {
    id: 'pin-1',
    lat: 14.6,
    lng: 121,
    capturedAt: '2026-10-30T10:00:00Z',
    mode: 'live',
    flags: 0,
    gpsAccuracyM: 10,
    level,
    landmark: 'hub',
    passability: PASSABILITY[level],
    levelIsFloor: false,
    basis: { vehicles: 1, people: 0 },
    ...extra,
  }
}

describe('a level result', () => {
  it('shows the level, landmark, class, time and place, and basis of a knee result, each on its own line', async () => {
    const result = await takePhoto()
    renderCard({ result, fixAccuracyM: 99, now: laterBy25(result) })

    expect(screen.getByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
    // The landmark is also listed under Details, with the other references.
    expect(outsideDetails("Water reaches three quarters of the way up a parked car's wheel rim.")).toHaveLength(1)
    expect(screen.getByText('Measured from the size of the wheel rim.')).toBeTruthy()
    expect(screen.getByText('Estimated 15 to 18 in.')).toBeTruthy()
    expect(screen.getByText('MMDA lists this level as not passable to light vehicles (NPLV).')).toBeTruthy()
    // The API's accuracy wins over the fix's.
    expect(screen.getByText('Photo taken 25 min ago. Location within 12 m.')).toBeTruthy()
    expect(screen.getByText('From 2 reference objects.')).toBeTruthy()
    expect(screen.getByTestId('gauge')).toBeTruthy()
  })

  it('uses the fix\'s accuracy when the API sends none (N1), and leaves the accuracy out when neither is known', async () => {
    const result = { ...(await takePhoto()), gpsAccuracyM: undefined }
    renderCard({ result, fixAccuracyM: 8.2, now: laterBy25(result) })
    expect(screen.getByText('Photo taken 25 min ago. Location within 9 m.')).toBeTruthy()
    cleanup()

    renderCard({ result, now: laterBy25(result) })
    expect(screen.getByText('Photo taken 25 min ago.')).toBeTruthy()
    expect(screen.queryByText(/Location within/)).toBeNull()
  })

  it('shows a floor as "At least", with the top of the gauge open', async () => {
    const result = await takePhoto('level_floor')
    renderCard({ result })
    expect(screen.getByText('At least tire deep at this spot (MMDA level).')).toBeTruthy()
    expect(screen.getByText('MMDA lists this level as not passable to any vehicle (NPATV).')).toBeTruthy()
    expect(screen.getByTestId('gauge').getAttribute('data-open')).toBe('true')
  })

  it('shows both added levels without "(MMDA level)", each with the MMDA level it lies beyond', async () => {
    renderCard({ result: await takePhoto('level_below_gutter') })
    expect(screen.getByText('Below gutter deep at this spot.')).toBeTruthy()
    expect(screen.getByText("Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).")).toBeTruthy()
    cleanup()

    renderCard({ result: await takePhoto('level_above_chest') })
    expect(screen.getByText('Above chest deep at this spot.')).toBeTruthy()
    expect(screen.getByText("Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).")).toBeTruthy()
  })

  it('shows the inches line only when both ends are there, and the geometry line only for geometry', async () => {
    const knee = await takePhoto()
    renderCard({ result: { ...knee, depthInMax: undefined } })
    expect(screen.queryByText(/Estimated/)).toBeNull()
    cleanup()
    renderCard({ result: { ...knee, depthInMin: undefined } })
    expect(screen.queryByText(/Estimated/)).toBeNull()
    cleanup()
    renderCard({ result: { ...knee, depthInMin: 15, depthInMax: 15 } })
    expect(screen.getByText('Estimated 15 in.')).toBeTruthy()
    cleanup()

    const landmark = await takePhoto('level_landmark')
    expect(landmark.levelFrom).toBe('landmark')
    renderCard({ result: landmark })
    expect(screen.queryByText(/Measured from/)).toBeNull()
    expect(screen.queryByText(/Estimated/)).toBeNull()
    expect(screen.getByText('Half-tire deep at this spot (MMDA level).')).toBeTruthy()
  })

  it('shows no basis line for a result that has none, as a saved sample result has', async () => {
    renderCard({ result: { ...(await takePhoto()), basis: undefined } })
    expect(screen.queryByText(/reference object/)).toBeNull()
  })

  it('wraps the level line in the live region', async () => {
    renderCard({ result: await takePhoto() })
    const status = screen.getByRole('status')
    expect(status.textContent).toContain('Knee deep at this spot (MMDA level).')
    expect(screen.getAllByRole('status')).toHaveLength(1)
  })

  it('links to MMDA\'s and PAGASA\'s official sites', async () => {
    renderCard({ result: await takePhoto() })
    const href = (name: string) => screen.getByRole('link', { name }).getAttribute('href')
    expect(href("MMDA's official site")).toBe('https://mmda.gov.ph/')
    expect(href("PAGASA's official site")).toBe('https://www.pagasa.dost.gov.ph/')
  })

  it('shows a live pin the same way, with the pin\'s own accuracy, and a pin\'s accuracy of null falls back to the fix', () => {
    const now = new Date('2026-10-30T10:25:00Z')
    renderCard({ result: pinAt('knee'), source: 'pin', now })
    expect(screen.getByText('Photo taken 25 min ago. Location within 10 m.')).toBeTruthy()
    expect(screen.getByText('From 1 reference object.')).toBeTruthy()
    cleanup()

    renderCard({ result: pinAt('knee', { gpsAccuracyM: null }), source: 'pin', now, fixAccuracyM: 14 })
    expect(screen.getByText('Photo taken 25 min ago. Location within 14 m.')).toBeTruthy()
  })

  it('shows "just now" for a photo from the future, and never "NaN" for a time it cannot read', () => {
    renderCard({ result: pinAt('knee'), source: 'pin', now: new Date('2026-10-30T09:00:00Z') })
    expect(screen.getByText('Photo taken just now. Location within 10 m.')).toBeTruthy()
    cleanup()
    renderCard({ result: pinAt('knee', { capturedAt: 'later' }), source: 'pin' })
    expect(screen.queryByText(/Photo taken/)).toBeNull()
    expect(text()).not.toMatch(/NaN|undefined|null/)
  })

  it('says "at this spot" on every level, in both languages, and "(MMDA level)" only on the seven gauge levels', () => {
    for (const [lang, spot] of [['en', 'at this spot'], ['fil', 'sa spot na ito']] as const) {
      for (const level of LEVELS) {
        for (const floor of [false, true]) {
          renderCard({ result: pinAt(level, { levelIsFloor: floor }), source: 'pin' }, lang)
          const headline = screen.getByRole('status').textContent ?? ''
          expect(headline, `${lang} ${level} ${floor}`).toContain(spot)
          expect(headline.includes('(MMDA level)'), `${lang} ${level}`).toBe(level !== 'below_gutter' && level !== 'above_chest')
          cleanup()
        }
      }
    }
  })
})

describe('the other outcomes', () => {
  it('"no flood seen" reads "No flood seen at this spot.", with an empty gauge and nothing a level would carry', async () => {
    renderCard({ result: await takePhoto('no_flood_seen') })
    expect(screen.getByRole('status').textContent).toContain('No flood seen at this spot.')
    const cells = [...screen.getByTestId('gauge').querySelectorAll<HTMLElement>('[data-cell]')]
    expect(cells).toHaveLength(9)
    expect(cells.every((cell) => cell.dataset.state === 'empty')).toBe(true)
    expect(text()).not.toMatch(/deep at this spot|MMDA lists|reference object|Estimated/)
  })

  it('a refusal shows D19\'s line and the reason line, with no frame around it', async () => {
    renderCard({ result: await takePhoto('refused_too_dark') })
    expect(screen.getByRole('status').textContent).toContain(D19)
    expect(screen.getByText('The photo is too dark to read.')).toBeTruthy()
    expect(text()).not.toContain("Lusot can't tell from this photo.")
    expect(text()).not.toContain('Someone reporting this spot would see:')
    expect(screen.queryByTestId('gauge')).toBeNull()
    expect(text()).not.toContain('Processing failed')
  })

  it('a failure reads "Processing failed, try again." with its reason line', async () => {
    renderCard({ result: await takePhoto('failed_pipeline_error') })
    expect(screen.getByRole('status').textContent).toContain('Processing failed, try again.')
    expect(screen.getByText('Lusot had an error while analyzing the photo.')).toBeTruthy()
    expect(text()).not.toContain(D19)
    expect(screen.queryByTestId('gauge')).toBeNull()
  })

  it('"Try again" on a failed card asks for a new photo and does nothing else, so the photo is never resent', async () => {
    const result = await takePhoto('failed_model_error')
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const onNewPhoto = vi.fn()
    const onCheckAgain = vi.fn()
    const onPhotoExpired = vi.fn()
    renderCard({ result, onNewPhoto, onCheckAgain, onPhotoExpired })

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(onNewPhoto).toHaveBeenCalledTimes(1)
    expect(onCheckAgain).not.toHaveBeenCalled()
    expect(onPhotoExpired).not.toHaveBeenCalled()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('has no "Try again" without a way to start a new photo, and none on a refusal or a level', async () => {
    renderCard({ result: await takePhoto('failed_model_error') })
    expect(screen.queryByRole('button')).toBeNull()
    cleanup()
    renderCard({ result: await takePhoto('refused_too_blurry'), onNewPhoto: vi.fn() })
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
    cleanup()
    renderCard({ result: await takePhoto(), onNewPhoto: vi.fn() })
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
  })

  it('a private result adds that it was taken outside Metro Manila, so it is not on the map', async () => {
    const result = await takePhoto('level_private')
    expect(result.mode).toBe('private')
    renderCard({ result })
    expect(screen.getByText("Taken outside Metro Manila, so only you see this result. It isn't on the map.")).toBeTruthy()
    expect(screen.getByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
    cleanup()
    renderCard({ result: await takePhoto() })
    expect(text()).not.toContain('Taken outside Metro Manila')
  })

  it('"No result yet" says so, with "Check again", and shows no level, outcome or gauge', async () => {
    const { fetchFn } = mockWith('pending_forever')
    const { reportId, upload } = await requestUpload(API, REQ, DEVICE, fetchFn)
    await postToS3(upload, JPEG, fetchFn)
    const pending = (await getReport(API, reportId, fetchFn)) as ReportResult
    const onCheckAgain = vi.fn()
    const onNewPhoto = vi.fn()
    renderCard({ result: pending, noResultYet: true, onCheckAgain, onNewPhoto })

    expect(screen.getByRole('status').textContent).toContain('No result yet. The analysis is taking longer than usual.')
    fireEvent.click(screen.getByRole('button', { name: 'Check again' }))
    expect(onCheckAgain).toHaveBeenCalledTimes(1)
    expect(onNewPhoto).not.toHaveBeenCalled()
    expect(screen.queryByTestId('gauge')).toBeNull()
    expect(text()).not.toMatch(/Processing failed|No flood seen|deep at this spot|tell from this photo/)
  })

  it('a report that has no final status is "No result yet" too, never a made-up outcome', async () => {
    const { fetchFn } = mockWith('pending_forever')
    const { reportId } = await requestUpload(API, REQ, DEVICE, fetchFn)
    const pending = (await getReport(API, reportId, fetchFn)) as ReportResult
    expect(pending.status).toBe('pending')
    renderCard({ result: pending })
    expect(screen.getByText('No result yet. The analysis is taking longer than usual.')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('a finished report with neither a level nor "no flood seen" is shown as a failure, not read', async () => {
    renderCard({ result: { ...(await takePhoto()), level: undefined, noFloodSeen: undefined } })
    expect(screen.getByRole('status').textContent).toContain('Processing failed, try again.')
    expect(screen.getByText('No further reason is available.')).toBeTruthy()
  })

  it('keeps the three outcomes apart: different words, different icons, different edges', async () => {
    const outcomes = [
      ['no-flood', await takePhoto('no_flood_seen')],
      ['cant-tell', await takePhoto('refused_too_dark')],
      ['failed', await takePhoto('failed_model_error')],
    ] as const
    const seen: { outcome: string | undefined; headline: string; icon: string | undefined; edge: string }[] = []
    for (const [, result] of outcomes) {
      const { container } = renderCard({ result })
      const card = container.querySelector<HTMLElement>('[data-outcome]') as HTMLElement
      seen.push({
        outcome: card.dataset.outcome,
        headline: screen.getByRole('status').textContent ?? '',
        icon: card.querySelector<HTMLElement>('[data-icon]')?.dataset.icon,
        edge: card.className.match(/border-(?:solid|dashed|dotted|double)/)?.[0] ?? '',
      })
      cleanup()
    }
    expect(seen.map((s) => s.outcome)).toEqual(outcomes.map(([name]) => name))
    for (const key of ['headline', 'icon', 'edge'] as const) expect(new Set(seen.map((s) => s[key])).size, key).toBe(3)
    expect(seen[0].headline).toBe('No flood seen at this spot.')
    expect(seen[2].headline).toMatch(/^Processing failed, try again\./)
    // None of the three reads as another: a dry reading never says "failed" or "can't tell", and so on.
    expect(seen[0].headline).not.toMatch(/failed|can't tell/i)
    expect(seen[1].headline).not.toMatch(/flood seen|failed/i)
    expect(seen[2].headline).not.toMatch(/flood seen|can't tell/i)
  })
})

describe('a pause', () => {
  it('a report that ended paused opens with the paused line, with no failure, reason or "Try again"', async () => {
    const result = await takePhoto('failed_model_calls_paused')
    expect(result.refusalReason).toBe('model_calls_paused')
    renderCard({ result, onNewPhoto: vi.fn() })

    const paused = 'New analyses are paused right now. The map and the Tested page still work.'
    expect(screen.getByRole('status').textContent).toBe(paused)
    expect(text()).not.toContain('Processing failed')
    expect(screen.queryByText('New analyses are paused right now.')).toBeNull() // the reason line
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Map' }).getAttribute('href')).toBe('#/map')
    expect(screen.getByRole('link', { name: 'Tested' }).getAttribute('href')).toBe('#/tested')
  })

  it('a sample\'s paused card sits on the Tested page, so it links to the map only', async () => {
    const result = await takePhoto('failed_model_calls_paused')
    renderCard({ result, source: 'sample' })
    expect(screen.getByRole('link', { name: 'Map' }).getAttribute('href')).toBe('#/map')
    expect(screen.queryByRole('link', { name: 'Tested' })).toBeNull()
    expect(text()).not.toContain('Processing failed')
  })

  it('shows the paused line on its own, for a screen that has no result, with its own links and note', () => {
    render(
      <LanguageProvider>
        <PausedNotice links={['map']}>
          <p>Nothing was uploaded.</p>
        </PausedNotice>
      </LanguageProvider>,
    )
    expect(screen.getByRole('status').textContent).toContain('New analyses are paused right now.')
    expect(screen.getByText('Nothing was uploaded.')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Map' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Tested' })).toBeNull()
  })

  it('shows C638\'s Taglish line on a Taglish screen, unmarked, now that the M20 review has passed it', async () => {
    renderCard({ result: await takePhoto('failed_model_calls_paused') }, 'fil')
    const line = screen.getByText(FIL['result.paused'].text)
    expect(line.getAttribute('lang')).toBeNull()
    expect(line.closest('[lang="en"]')).toBeNull()
    expect(FIL['result.paused'].text).toBe(
      'Naka-pause ngayon ang mga bagong analysis. Gumagana pa rin ang mapa at ang Tested page.',
    )
    expect(FIL['result.paused'].reviewed).toBe(true)
    expect(EN['result.paused'].reviewed).toBe(true)
    expect(unreviewedKeys()).not.toContainEqual({ lang: 'fil', key: 'result.paused' })
  })

  it('serves a saved sample: the paused line, then its saved result marked with its date, and no basis, overlay or inches', async () => {
    const { fetchFn } = mockWith('failed_model_calls_paused')
    const samples = await getSamples(API, fetchFn)
    const saved = (await runSample(API, samples[0].sampleId, DEVICE, fetchFn)) as SavedSample
    expect(saved.saved).toBe(true)
    const result = { reportId: '', mode: 'sample', published: false, ...saved.result } as ReportResult
    renderCard({ result, source: 'sample', sample: samples[0], savedAt: saved.savedAt })

    // The paused line comes first, in its own live region; the saved result follows in another, marked with its date.
    const [paused, reading] = screen.getAllByRole('status').map((region) => region.textContent ?? '')
    expect(screen.getAllByRole('status')).toHaveLength(2)
    expect(paused).toBe('New analyses are paused right now. The map and the Tested page still work.')
    expect(reading).toContain('Saved result from Oct 29, 2026')
    expect(reading).toContain('Knee deep at this spot (MMDA level).')
    expect(screen.getByText('This is a saved reading of a credited photo, not a test result.')).toBeTruthy()
    expect(text().indexOf('New analyses are paused')).toBeLessThan(text().indexOf('Photo from'))
    expect(text()).not.toContain('live reading')
    expect(text()).not.toMatch(/reference object|Estimated|Measured from|Photo taken|Location within/)
    expect(screen.getByRole('link', { name: 'Map' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Tested' })).toBeNull()
  })

  it('keeps a saved card bare itself: no inches, geometry line, basis or references, even from a full live result', async () => {
    // The API client drops these fields from a saved answer, but the card doesn't rely on that (amendment 10).
    const live = await takePhoto()
    expect(live).toMatchObject({ levelFrom: 'geometry', depthInMin: 15, basis: { vehicles: 1, people: 1 } })
    expect(live.readings).toHaveLength(3)
    const { container } = renderCard({
      result: { ...live, mode: 'sample' },
      source: 'sample',
      savedAt: '2026-10-29T14:20:00Z',
    })

    expect(screen.getByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
    expect(screen.getByText('MMDA lists this level as not passable to light vehicles (NPLV).')).toBeTruthy()
    expect(screen.getByText('This is a saved reading of a credited photo, not a test result.')).toBeTruthy()
    expect(text()).not.toMatch(/Estimated|Measured from|reference object|Reference \d|Reference objects|Not used/)
    expect(container.querySelector('details')).toBeNull()
    cleanup()

    // A live card with the same result keeps all of them.
    renderCard({ result: live, source: 'own' })
    expect(text()).toMatch(/Estimated 15 to 18 in\./)
    expect(text()).toContain('Measured from the size of the wheel rim.')
    expect(text()).toContain('From 2 reference objects.')
  })

  it('a saved sample that was refused gets the sample frame, and one with no flood says so', async () => {
    const refused: ReportResult = {
      reportId: '',
      status: 'refused',
      refusalReason: 'no_usable_reference',
      mode: 'sample',
      published: false,
    }
    renderCard({ result: refused, source: 'sample', savedAt: '2026-10-29T14:20:00Z' })
    expect(screen.getByText("Lusot can't tell from this photo.")).toBeTruthy()
    expect(screen.getByText('Someone reporting this spot would see:')).toBeTruthy()
    expect(screen.getByText(D19)).toBeTruthy()
    cleanup()

    const dry: ReportResult = { reportId: '', status: 'done', noFloodSeen: true, mode: 'sample', published: false }
    renderCard({ result: dry, source: 'sample', savedAt: '2026-10-29T14:20:00Z' })
    const reading = screen.getAllByRole('status')[1].textContent
    expect(reading).toContain('No flood seen at this spot.')
    expect(reading).toContain('Saved result from Oct 29, 2026')
  })
})

describe('a sample and a demo pin', () => {
  async function sampleRun(scenario?: Scenario) {
    const { fetchFn, c } = mockWith(scenario)
    const samples = await getSamples(API, fetchFn)
    const started = (await runSample(API, samples[0].sampleId, DEVICE, fetchFn)) as { reportId: string }
    const result = await pollReport(API, started.reportId, { fetchFn, sleep: c.sleep, now: c.now })
    return { sample: samples[0], result }
  }

  it('shows the blurred photo, where and when it is from, its credit, what Lusot did to it, and that it is a live reading', async () => {
    const { sample, result } = await sampleRun()
    renderCard({ result, source: 'sample', sample })

    const photo = screen.getByRole('img', { name: 'The photo, with faces and plates blurred.' })
    expect(photo.getAttribute('src')).toBe(sample.photoUrl)
    expect(screen.getByText('Photo from Sep 26, 2009, Marikina, Typhoon Ondoy')).toBeTruthy()
    expect(screen.getByText('Photo: Example Contributor (mock), CC0 1.0')).toBeTruthy()
    expect(screen.getByText('Lusot blurred the faces and plates in this photo. Lusot drew its outlines on it.')).toBeTruthy()
    expect(screen.getByText('This is a live reading of a credited photo, not a test result.')).toBeTruthy()
    expect(screen.getByText('Sample')).toBeTruthy()
    expect(screen.getByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
    expect(text()).not.toMatch(/Photo taken|Location within|ago\b/)
  })

  it('shows the photo and its credit whatever the outcome, and asks for a new link when the photo fails to load', async () => {
    const { sample, result } = await sampleRun('no_flood_seen')
    const onPhotoExpired = vi.fn()
    renderCard({ result, source: 'sample', sample, onPhotoExpired })

    expect(screen.getByRole('status').textContent).toContain('No flood seen at this spot.')
    const photo = screen.getByRole('img')
    expect(onPhotoExpired).not.toHaveBeenCalled()
    fireEvent.error(photo)
    expect(onPhotoExpired).toHaveBeenCalledTimes(1)
  })

  it('shows a refused sample as "Lusot can\'t tell from this photo.", its reason, then what someone reporting this spot would see', async () => {
    const { sample, result } = await sampleRun('refused_no_usable_reference')
    expect(result.status).toBe('refused')
    renderCard({ result, source: 'sample', sample })

    const status = screen.getByRole('status').textContent ?? ''
    expect(status).toContain("Lusot can't tell from this photo.")
    expect(screen.getByText('No car or person in the photo could be used to read the depth.')).toBeTruthy()
    const framing = screen.getByText('Someone reporting this spot would see:')
    const d19 = screen.getByText(D19)
    expect(framing.compareDocumentPosition(d19) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // D19 sits after its frame, and the plain reason sits before it.
    const reason = screen.getByText('No car or person in the photo could be used to read the depth.')
    expect(reason.compareDocumentPosition(framing) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  // The caption says what Lusot did to the photo. It claims outlines (spec C617) only when there are some to show.
  const BLURRED = 'Lusot blurred the faces and plates in this photo.'
  const OUTLINES = 'Lusot drew its outlines on it.'
  const caption = () => (screen.getByRole('img').closest('figure') as HTMLElement).querySelector('figcaption')?.textContent ?? ''

  it('says it drew outlines on a level result that links its overlay, after saying it blurred faces and plates', async () => {
    const { sample, result } = await sampleRun()
    expect(result).toMatchObject({ level: 'knee' })
    expect(result.overlayUrl ?? result.layersUrl).toBeDefined()
    renderCard({ result, source: 'sample', sample })

    expect(caption()).toContain(`${BLURRED} ${OUTLINES}`)
    expect(EN['sample.edited'].text).not.toMatch(/outline/i)
  })

  it('says it blurred faces and plates and nothing about outlines on a result with none to show', async () => {
    for (const scenario of ['no_flood_seen', 'refused_no_usable_reference'] as const) {
      const { sample, result } = await sampleRun(scenario)
      expect(result.overlayUrl ?? result.layersUrl, scenario).toBeUndefined()
      renderCard({ result, source: 'sample', sample })
      expect(caption(), scenario).toContain(BLURRED)
      expect(caption(), scenario).not.toMatch(/outline/i)
      cleanup()
    }
    // A level result with its links gone has no outlines either.
    const { sample, result } = await sampleRun()
    renderCard({ result: { ...result, overlayUrl: undefined, layersUrl: undefined }, source: 'sample', sample })
    expect(caption()).toContain(BLURRED)
    expect(caption()).not.toMatch(/outline/i)
  })

  it('never says it drew outlines on a saved sample, even from a full live result', async () => {
    const { sample, result } = await sampleRun()
    expect(result.layersUrl).toBeDefined()
    renderCard({ result, source: 'sample', sample, savedAt: '2026-10-29T14:20:00Z' })
    expect(caption()).toContain(BLURRED)
    expect(caption()).not.toMatch(/outline/i)
    cleanup()

    // What a saved answer is, as the API client gives it: no links at all.
    const { fetchFn } = mockWith('failed_model_calls_paused')
    const samples = await getSamples(API, fetchFn)
    const saved = (await runSample(API, samples[0].sampleId, DEVICE, fetchFn)) as SavedSample
    const bare = { reportId: '', mode: 'sample', published: false, ...saved.result } as ReportResult
    renderCard({ result: bare, source: 'sample', sample: samples[0], savedAt: saved.savedAt })
    expect(caption()).toContain(BLURRED)
    expect(caption()).not.toMatch(/outline/i)
  })

  it('says it drew outlines on a demo pin that links its overlay, and not on a pin that carries no links', async () => {
    const { fetchFn } = mockWith()
    const demo = (await getPins(API, fetchFn)).find((pin) => pin.mode === 'demo') as Pin
    const report = (await getReport(API, demo.id, fetchFn)) as ReportResult
    expect(report.mode).toBe('demo')
    renderCard({ result: { ...report, credit: PLAIN_CREDIT }, source: 'pin' })
    expect(caption()).toContain(`${BLURRED} ${OUTLINES}`)
    cleanup()

    renderCard({ result: { ...demo, credit: PLAIN_CREDIT }, source: 'pin', photoUrl: report.photoUrl })
    expect(caption()).toContain(BLURRED)
    expect(caption()).not.toMatch(/outline/i)
  })

  // The credit states how Lusot changed the photo (C617's CC BY change note), so the card says each change once. MS4's
  // sample credit states the blur only, since the stored photo has no outlines; its demo pin credit states both.
  const CHANGED_CREDIT = 'Photo: Example Contributor (mock), CC BY 4.0. Faces and plates blurred by Lusot.'
  const DEMO_CREDIT = 'Photo: Example Contributor (mock), CC BY 4.0. Faces and plates blurred, and outlines drawn, by Lusot.'

  it("says only that it drew outlines when the sample's credit already says the photo was blurred", async () => {
    const { sample, result } = await sampleRun()
    expect(result.overlayUrl ?? result.layersUrl).toBeDefined()
    renderCard({ result, source: 'sample', sample: { ...sample, credit: CHANGED_CREDIT } })

    expect(caption()).toContain(CHANGED_CREDIT)
    expect(text()).not.toContain(BLURRED)
    expect(screen.getByText(OUTLINES)).toBeTruthy()
    cleanup()

    // Any case counts, and the whole word: "Blurred" states it, "unblurred" does not.
    renderCard({ result, source: 'sample', sample: { ...sample, credit: 'Photo: Someone. Blurred by Lusot.' } })
    expect(text()).not.toContain(BLURRED)
    expect(screen.getByText(OUTLINES)).toBeTruthy()
    cleanup()
    renderCard({ result, source: 'sample', sample: { ...sample, credit: 'Photo: Someone. Unblurred original.' } })
    expect(caption()).toContain(`${BLURRED} ${OUTLINES}`)
  })

  it("has no line of its own when the sample's credit says the photo was blurred and there are no outlines to show", async () => {
    for (const scenario of ['no_flood_seen', 'refused_no_usable_reference'] as const) {
      const { sample, result } = await sampleRun(scenario)
      renderCard({ result, source: 'sample', sample: { ...sample, credit: CHANGED_CREDIT } })
      expect(caption(), scenario).toContain(CHANGED_CREDIT)
      expect(text(), scenario).not.toContain(BLURRED)
      expect(text(), scenario).not.toMatch(/outline/i)
      cleanup()
    }
    const { sample, result } = await sampleRun()
    renderCard({
      result: { ...result, overlayUrl: undefined, layersUrl: undefined },
      source: 'sample',
      sample: { ...sample, credit: CHANGED_CREDIT },
    })
    expect(text()).not.toContain(BLURRED)
    expect(text()).not.toMatch(/outline/i)
    // The caption holds the credit and nothing after it.
    const figcaption = (screen.getByRole('img').closest('figure') as HTMLElement).querySelector('figcaption') as HTMLElement
    expect(figcaption.lastElementChild?.textContent).toBe(CHANGED_CREDIT)
  })

  it('keeps its own blurred line and its outlines rule when the credit does not say the photo was blurred', async () => {
    const { sample, result } = await sampleRun()
    expect(sample.credit).not.toMatch(/blurred/i)
    renderCard({ result, source: 'sample', sample })
    expect(caption()).toContain(`${BLURRED} ${OUTLINES}`)
    cleanup()

    renderCard({ result: { ...result, overlayUrl: undefined, layersUrl: undefined }, source: 'sample', sample })
    expect(caption()).toContain(BLURRED)
    expect(caption()).not.toMatch(/outline/i)
  })

  it("says nothing more on a demo pin whose credit names the blur and the outlines, with or without the photo", async () => {
    const { fetchFn } = mockWith()
    const demo = (await getPins(API, fetchFn)).find((pin) => pin.mode === 'demo') as Pin
    const report = (await getReport(API, demo.id, fetchFn)) as ReportResult
    expect(report.overlayUrl ?? report.layersUrl).toBeDefined()
    renderCard({ result: { ...report, credit: DEMO_CREDIT }, source: 'pin' })
    expect(caption()).toContain(DEMO_CREDIT)
    expect(text()).not.toContain(BLURRED)
    expect(text()).not.toContain(OUTLINES)
    cleanup()

    renderCard({ result: { ...demo, credit: DEMO_CREDIT }, source: 'pin' })
    expect(screen.getByText(DEMO_CREDIT)).toBeTruthy()
    expect(text()).not.toContain(BLURRED)
    expect(text()).not.toContain(OUTLINES)
    cleanup()

    // The mock's demo credit names the blur only, so the card adds its outlines line and nothing else.
    expect(demo.credit).toMatch(/\bblurred\b/i)
    expect(demo.credit).not.toMatch(/outline/i)
    renderCard({ result: report, source: 'pin' })
    expect(text()).not.toContain(BLURRED)
    expect(screen.getByText(OUTLINES)).toBeTruthy()
  })

  it('leaves out a place or event of "unknown" on a sample card and a demo pin, and shows a real one as written', async () => {
    const { sample, result } = await sampleRun()
    renderCard({ result, source: 'sample', sample: { ...sample, place: 'unknown', event: 'Typhoon Ondoy' } })
    expect(screen.getByText('Photo from Sep 26, 2009, Typhoon Ondoy')).toBeTruthy()
    expect(text()).not.toMatch(/unknown/i)
    cleanup()

    renderCard({ result, source: 'sample', sample: { ...sample, place: 'Unknown ', event: 'Typhoon Ondoy' } })
    expect(screen.getByText('Photo from Sep 26, 2009, Typhoon Ondoy')).toBeTruthy()
    cleanup()

    renderCard({ result, source: 'sample', sample: { ...sample, place: 'Baliuag, Bulacan', event: 'Typhoon Ondoy' } })
    expect(screen.getByText('Photo from Sep 26, 2009, Baliuag, Bulacan, Typhoon Ondoy')).toBeTruthy()
    cleanup()

    const { fetchFn } = mockWith()
    const demo = (await getPins(API, fetchFn)).find((pin) => pin.mode === 'demo') as Pin
    renderCard({ result: { ...demo, place: 'unknown' }, source: 'pin' })
    expect(screen.getByText('Photo from Sep 26, 2009, Typhoon Ondoy')).toBeTruthy()
    expect(text()).not.toMatch(/unknown/i)
  })

  it('says both lines in Taglish on a Taglish screen, now that they are reviewed', async () => {
    const { sample, result } = await sampleRun()
    renderCard({ result, source: 'sample', sample }, 'fil')
    expect(FIL['sample.edited'].reviewed && FIL['sample.outlines'].reviewed).toBe(true)
    expect(caption()).toContain(`${FIL['sample.edited'].text} ${FIL['sample.outlines'].text}`)
    expect(FIL['sample.outlines'].text).toBe('Iginuhit ng Lusot ang mga outline nito sa photo.')
  })

  it('a demo pin does the same: the Demo badge, its own date and place, its credit, and no accuracy line', async () => {
    const { fetchFn } = mockWith()
    const pins = await getPins(API, fetchFn)
    const demo = pins.find((pin) => pin.mode === 'demo') as Pin
    const report = (await getReport(API, demo.id, fetchFn)) as ReportResult
    renderCard({ result: demo, source: 'pin', photoUrl: report.photoUrl })

    expect(screen.getByText('Demo')).toBeTruthy()
    expect(screen.getByRole('img').getAttribute('src')).toBe(report.photoUrl)
    expect(screen.getByText('Photo from Sep 26, 2009, Marikina, Typhoon Ondoy')).toBeTruthy()
    expect(screen.getByText(demo.credit as string)).toBeTruthy()
    expect(screen.getByText('Above chest deep at this spot.')).toBeTruthy()
    expect(text()).not.toMatch(/Photo taken|Location within/)
    expect(screen.queryByText('Sample')).toBeNull()
  })

  // I1: a demo pin's reading was made once, at seeding, of a photo from another day, so its card never calls it live.
  // The Demo badge and the photo's own date say what it is. A sample's run is live, and its card says so.
  it('never says a demo pin is a live reading, with or without its photo, and a sample run still says it', async () => {
    const LIVE = 'This is a live reading of a credited photo, not a test result.'
    const { fetchFn } = mockWith()
    const demo = (await getPins(API, fetchFn)).find((pin) => pin.mode === 'demo') as Pin
    const report = (await getReport(API, demo.id, fetchFn)) as ReportResult
    for (const result of [demo, report]) {
      renderCard({ result, source: 'pin' })
      expect(screen.getByText('Demo')).toBeTruthy()
      expect(screen.getByText('Above chest deep at this spot.')).toBeTruthy()
      expect(text()).not.toContain('live reading')
      expect(text()).not.toContain('saved reading')
      cleanup()
    }

    const { sample, result } = await sampleRun()
    renderCard({ result, source: 'sample', sample })
    expect(screen.getByText(LIVE)).toBeTruthy()
  })

  it('marks the credit as English on a Taglish screen', async () => {
    const { sample, result } = await sampleRun()
    renderCard({ result, source: 'sample', sample }, 'fil')
    const credit = screen.getByText('Photo: Example Contributor (mock), CC0 1.0')
    expect(credit.getAttribute('lang')).toBe('en')
  })

  it('a live card has no sample frame: no badge, no credit, no photo date and no claim that the reading is of a credited photo', async () => {
    const result = await takePhoto()
    expect(result.photoUrl).toBeDefined()
    renderCard({ result })
    await screen.findByTestId('overlay-svg')
    expect(text()).not.toMatch(/credited photo|Photo from|Sample|Demo/)
  })
})

// Task 14: the photo with Lusot's evidence drawn on it, in the card, for a level result with photo links.
describe('the photo and its overlay', () => {
  const BLURRED = 'Lusot blurred the faces and plates in this photo.'
  const OUTLINES = 'Lusot drew its outlines on it.'
  const PHOTO_ALT = 'The photo, with faces and plates blurred.'
  const figure = () => screen.getByRole('img', { name: PHOTO_ALT }).closest('figure') as HTMLElement
  const caption = () => figure().querySelector('figcaption')?.textContent ?? ''
  const after = (first: Node, second: Node) => Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)
  const emptyLayers = { version: 1, width: 800, height: 600, water: [], refs: [] }
  const answering = (body: unknown) => {
    net.fetch = async () => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
  }
  async function sampleRun() {
    const run = mockWith()
    const samples = await getSamples(API, run.fetchFn)
    const started = (await runSample(API, samples[0].sampleId, DEVICE, run.fetchFn)) as { reportId: string }
    const result = await pollReport(API, started.reportId, { fetchFn: run.fetchFn, sleep: run.c.sleep, now: run.c.now })
    return { sample: samples[0], result }
  }

  it("shows a live level result's blurred photo with the overlay on it, under the level line so that line stays first", async () => {
    const result = await takePhoto()
    renderCard({ result })
    const svg = await screen.findByTestId('overlay-svg')

    const photo = screen.getByRole('img', { name: PHOTO_ALT })
    expect(photo.getAttribute('src')).toBe(result.photoUrl)
    expect(svg.parentElement).toBe(photo.parentElement)
    expect(figure().parentElement?.tagName).toBe('ARTICLE')
    // The level line, then the gauge's block, then the photo: the reading is on the first screen at 360 x 640.
    const level = screen.getByText('Knee deep at this spot (MMDA level).')
    expect(after(level, figure())).toBe(true)
    expect(after(screen.getByTestId('gauge'), figure())).toBe(true)
    expect(caption()).toBe(`${BLURRED} ${OUTLINES}`)
    // Every reference is listed under the photo in the figure, with the cause on the one it left out (C615).
    const legend = within(figure()).getByRole('list')
    expect(within(legend).getAllByRole('listitem')).toHaveLength(3)
    expect(within(legend).getByText('Person 3: Not used, since this person may not be an adult.')).toBeTruthy()
    expect(after(svg, legend)).toBe(true)
    expect(after(legend, figure().querySelector('figcaption') as Node)).toBe(true)
  })

  it("shows the same on a floor reading, labelled as a floor, as the card's level line is", async () => {
    const result = await takePhoto('level_floor')
    renderCard({ result })
    const svg = await screen.findByTestId('overlay-svg')
    expect(screen.getByText('At least tire deep at this spot (MMDA level).')).toBeTruthy()
    expect(svg.querySelector('[data-layer="label"] text')?.textContent).toBe('1: At least tire')
  })

  it('shows the same in Taglish, with the floor as "Hindi bababa sa"', async () => {
    const result = await takePhoto('level_floor')
    renderCard({ result }, 'fil')
    const svg = await screen.findByTestId('overlay-svg')
    expect(svg.querySelector('[data-layer="label"] text')?.textContent).toBe('1: Hindi bababa sa tire')
    const legend = within(screen.getByRole('figure')).getByRole('list', { name: FIL['overlay.title'].text })
    expect(within(legend).getAllByRole('listitem')[0].textContent).toMatch(/^Gulong 1: Hindi bababa sa tire\. /)
  })

  it('has no photo for a pin card with no links, or a result with no photo link', async () => {
    renderCard({ result: pinAt('knee') })
    expect(screen.queryByRole('img')).toBeNull()
    cleanup()
    const result = await takePhoto()
    renderCard({ result: { ...result, photoUrl: undefined } })
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByRole('figure')).toBeNull()
  })

  it('has no photo for a refusal, a failure or no flood seen, which carry no links', async () => {
    for (const scenario of ['no_flood_seen', 'refused_no_usable_reference', 'failed_model_error'] as const) {
      renderCard({ result: await takePhoto(scenario) })
      expect(screen.queryByRole('figure'), scenario).toBeNull()
      cleanup()
    }
  })

  it('shows the photo and the blurred line and nothing about outlines when the result links no overlay', async () => {
    const result = await takePhoto()
    renderCard({ result: { ...result, overlayUrl: undefined, layersUrl: undefined } })
    expect(screen.getByRole('img', { name: PHOTO_ALT })).toBeTruthy()
    expect(caption()).toBe(BLURRED)
    await act(async () => {})
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
  })

  it('says it drew outlines only while the layers hold some: an empty file takes the claim back, a full one keeps it', async () => {
    const result = await takePhoto()
    answering(emptyLayers)
    renderCard({ result })
    // Before the layers answer, the link says there are outlines.
    expect(caption()).toContain(OUTLINES)
    await act(async () => {})
    expect(caption()).toBe(BLURRED)
    cleanup()

    answering({ ...emptyLayers, water: levelLayers('knee').water })
    renderCard({ result })
    await screen.findByTestId('overlay-svg')
    expect(caption()).toBe(`${BLURRED} ${OUTLINES}`)
    cleanup()

    answering({ ...emptyLayers, refs: levelLayers('knee').refs })
    renderCard({ result })
    await screen.findByTestId('overlay-svg')
    expect(caption()).toBe(`${BLURRED} ${OUTLINES}`)
  })

  it("keeps today's rule when the layers can't be read: an overlay link keeps the claim, and the JPEG is drawn over the photo", async () => {
    const result = await takePhoto()
    net.fetch = () => Promise.reject(new TypeError('Failed to fetch'))
    const { container } = renderCard({ result })
    await act(async () => {})
    expect(caption()).toBe(`${BLURRED} ${OUTLINES}`)
    expect(container.querySelector(`img[src="${result.overlayUrl}"]`)).toBeTruthy()
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
  })

  it('draws the same overlay on a sample and on a demo pin, since each is a level result with links', async () => {
    const { sample, result } = await sampleRun()
    renderCard({ result, source: 'sample', sample })
    const sampleSvg = await screen.findByTestId('overlay-svg')
    expect(sampleSvg.querySelectorAll('[data-ref]')).toHaveLength(3)
    cleanup()

    const { fetchFn } = mockWith()
    const demo = (await getPins(API, fetchFn)).find((pin) => pin.mode === 'demo') as Pin
    const report = (await getReport(API, demo.id, fetchFn)) as ReportResult
    renderCard({ result: report, source: 'pin' })
    const demoSvg = await screen.findByTestId('overlay-svg')
    expect(demoSvg.querySelectorAll('[data-ref]').length).toBeGreaterThan(0)
  })

  it('never draws it on a saved sample, even from a full live result, and never asks for its layers', async () => {
    const { sample, result } = await sampleRun()
    expect(result.layersUrl).toBeDefined()
    const asked = vi.fn<typeof fetch>(net.fetch)
    net.fetch = asked
    const { container } = renderCard({ result, source: 'sample', sample, savedAt: '2026-10-29T14:20:00Z' })
    await act(async () => {})

    expect(asked).not.toHaveBeenCalled()
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
    expect(container.querySelector('[data-layer]')).toBeNull()
    expect(container.querySelectorAll('img')).toHaveLength(1)
  })

  it('asks for a new link once when the photo fails to load, and a second failure leaves the card without the photo, not an error', async () => {
    const result = await takePhoto()
    const onPhotoExpired = vi.fn()
    renderCard({ result, onPhotoExpired })
    await screen.findByTestId('overlay-svg')

    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    expect(onPhotoExpired).toHaveBeenCalledTimes(1)
    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    expect(onPhotoExpired).toHaveBeenCalledTimes(1)

    expect(screen.queryByRole('img', { name: PHOTO_ALT })).toBeNull()
    expect(screen.queryByTestId('overlay-svg')).toBeNull()
    expect(screen.queryByRole('figure')).toBeNull()
    expect(text()).not.toContain(BLURRED)
    // The legend goes with the photo; Details still lists each reference.
    expect(screen.queryByText('Person 3: Not used, since this person may not be an adult.')).toBeNull()
    expect(screen.queryByRole('list', { name: EN['overlay.title'].text })).toBeNull()
    // The reading is all still there, and nothing says something went wrong.
    expect(screen.getByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(text()).not.toMatch(/error|failed|couldn't/i)
  })

  it('takes back what an example card said about its photo when the photo is gone, and keeps its credit and date', async () => {
    const { sample, result } = await sampleRun()
    renderCard({ result, source: 'sample', sample, onPhotoExpired: vi.fn() })
    await screen.findByTestId('overlay-svg')
    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    expect(screen.queryByRole('img', { name: PHOTO_ALT })).toBeNull()
    expect(text()).not.toContain(BLURRED)
    expect(text()).not.toContain(OUTLINES)
    expect(screen.queryByRole('list', { name: EN['overlay.title'].text })).toBeNull()
    expect(screen.getByText('Photo from Sep 26, 2009, Marikina, Typhoon Ondoy')).toBeTruthy()
    expect(screen.getByText('Photo: Example Contributor (mock), CC0 1.0')).toBeTruthy()
  })

  // I2: a demo pin's card is ordered as a live card is: the badge, the level line, the gauge block, then the photo with
  // its credit. The Tested page's sample card keeps its photo first (the controller's call).
  async function demoReport() {
    const { fetchFn } = mockWith()
    const demo = (await getPins(API, fetchFn)).find((pin) => pin.mode === 'demo') as Pin
    return (await getReport(API, demo.id, fetchFn)) as ReportResult
  }

  it("puts a demo pin's photo under the gauge block, after the Demo badge and the level line, so the line is on the first screen", async () => {
    renderCard({ result: { ...(await demoReport()), credit: PLAIN_CREDIT }, source: 'pin' })
    await screen.findByTestId('overlay-svg')

    const badge = screen.getByText('Demo')
    const level = screen.getByText('Above chest deep at this spot.')
    const gauge = screen.getByTestId('gauge')
    expect(after(badge, level)).toBe(true)
    expect(after(level, gauge)).toBe(true)
    expect(after(gauge, figure())).toBe(true)
    // Its credit and date stay with the photo, under it, and the badge is not inside the figure.
    expect(figure().contains(badge)).toBe(false)
    const photo = screen.getByRole('img', { name: PHOTO_ALT })
    const from = screen.getByText('Photo from Sep 26, 2009, Marikina, Typhoon Ondoy')
    expect(figure().contains(from)).toBe(true)
    expect(after(photo, from)).toBe(true)
    expect(after(within(figure()).getByRole('list'), from)).toBe(true)
    expect(caption()).toContain(`${BLURRED} ${OUTLINES}`)
    // The rest of the card is still there, after the photo, with no claim that the demo reading is live (I1).
    expect(after(figure(), screen.getByRole('list', { name: 'Official advisories' }))).toBe(true)
    expect(text()).not.toContain('live reading')
  })

  it('keeps a demo pin that has no photo as it was: the badge, the level line, then its credit and the blurred line', async () => {
    const { fetchFn } = mockWith()
    const demo = (await getPins(API, fetchFn)).find((pin) => pin.mode === 'demo') as Pin
    renderCard({ result: { ...demo, credit: PLAIN_CREDIT }, source: 'pin' })
    expect(screen.queryByRole('img')).toBeNull()
    expect(after(screen.getByText('Demo'), screen.getByText('Above chest deep at this spot.'))).toBe(true)
    expect(screen.getByText(PLAIN_CREDIT)).toBeTruthy()
    expect(screen.getByText(BLURRED)).toBeTruthy()
  })

  it("leaves a sample card's photo first, as the Tested page has it, with the Sample badge inside the figure", async () => {
    const { sample, result } = await sampleRun()
    renderCard({ result, source: 'sample', sample })
    await screen.findByTestId('overlay-svg')
    expect(figure().contains(screen.getByText('Sample'))).toBe(true)
    expect(after(figure(), screen.getByText('Knee deep at this spot (MMDA level).'))).toBe(true)
  })

  // M3: a sample card's refreshed photo link is the one it shows.
  it("shows a sample's refreshed photo link, not the old link its run's report carried", async () => {
    const { sample, result } = await sampleRun()
    const linked = { ...result, photoUrl: 'https://photos.example.test/report-link.jpg' }
    const onPhotoExpired = vi.fn()
    const first = { ...sample, photoUrl: 'https://photos.example.test/sample-link-1.jpg' }
    const view = renderCard({ result: linked, source: 'sample', sample: first, onPhotoExpired })
    expect(screen.getByRole('img', { name: PHOTO_ALT }).getAttribute('src')).toBe(first.photoUrl)

    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    expect(onPhotoExpired).toHaveBeenCalledTimes(1)
    // The Tested page refreshes the list's links, so the card gets the sample again with a new one.
    const fresh = { ...sample, photoUrl: 'https://photos.example.test/sample-link-2.jpg' }
    view.rerender(
      <LanguageProvider>
        <ResultCard result={linked} source="sample" sample={fresh} onPhotoExpired={onPhotoExpired} />
      </LanguageProvider>,
    )
    expect(screen.getByRole('img', { name: PHOTO_ALT }).getAttribute('src')).toBe(fresh.photoUrl)
    await act(async () => {})
  })

  it("falls back to the run's own photo link when the sample has none", async () => {
    const { sample, result } = await sampleRun()
    const linked = { ...result, photoUrl: 'https://photos.example.test/report-link.jpg' }
    renderCard({ result: linked, source: 'sample', sample: { ...sample, photoUrl: undefined } })
    expect(screen.getByRole('img', { name: PHOTO_ALT }).getAttribute('src')).toBe(linked.photoUrl)
    await act(async () => {})
  })

  // M2: what a card remembers about its photo belongs to one result.
  it("keeps counting the photo's failures across a refreshed link of the same result, and gives it up on the second", async () => {
    const result = await takePhoto()
    const onPhotoExpired = vi.fn()
    const view = renderCard({ result, onPhotoExpired })
    await screen.findByTestId('overlay-svg')
    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    view.rerender(
      <LanguageProvider>
        <ResultCard result={{ ...result, photoUrl: 'https://photos.example.test/new.jpg' }} source="own" onPhotoExpired={onPhotoExpired} />
      </LanguageProvider>,
    )
    expect(screen.getByRole('img', { name: PHOTO_ALT }).getAttribute('src')).toBe('https://photos.example.test/new.jpg')
    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    expect(onPhotoExpired).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('img', { name: PHOTO_ALT })).toBeNull()
  })

  it('starts afresh for another result handed to the same card: the photo, its layers and its caption come back', async () => {
    const first = await takePhoto()
    const view = renderCard({ result: first, onPhotoExpired: vi.fn() })
    await screen.findByTestId('overlay-svg')
    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    fireEvent.error(screen.getByRole('img', { name: PHOTO_ALT }))
    expect(screen.queryByRole('img', { name: PHOTO_ALT })).toBeNull()

    const second = await takePhoto('level_floor')
    expect(second.reportId).not.toBe(first.reportId)
    view.rerender(
      <LanguageProvider>
        <ResultCard result={second} source="own" />
      </LanguageProvider>,
    )
    const svg = await screen.findByTestId('overlay-svg')
    expect(screen.getByRole('img', { name: PHOTO_ALT }).getAttribute('src')).toBe(second.photoUrl)
    expect(svg.querySelector('[data-layer="label"] text')?.textContent).toBe('1: At least tire')
    expect(caption()).toBe(`${BLURRED} ${OUTLINES}`)
  })

  it('forgets the layers of the last result too: an empty file for one does not hide the outlines of the next', async () => {
    const first = await takePhoto()
    answering(emptyLayers)
    const view = renderCard({ result: first })
    await act(async () => {})
    expect(caption()).toBe(BLURRED)

    const second = await takePhoto()
    view.rerender(
      <LanguageProvider>
        <ResultCard result={second} source="own" />
      </LanguageProvider>,
    )
    expect(caption()).toContain(OUTLINES)
    await screen.findByTestId('overlay-svg')
    expect(caption()).toBe(`${BLURRED} ${OUTLINES}`)
  })

  it("writes no link, report id or place into the card, and no banned or crossing words into the overlay's labels", async () => {
    const result = await takePhoto()
    const { container } = renderCard({ result })
    const svg = await screen.findByTestId('overlay-svg')
    const everything = svg.outerHTML + (container.textContent ?? '')
    expect(everything).not.toMatch(/r_[0-9a-f]{32}|sig=|https?:\/\/(?!www\.w3\.org|mmda\.gov\.ph|www\.pagasa)/)
    expect(everything).not.toContain(result.reportId)
    const labels = within(within(figure()).getByRole('list')).getAllByRole('listitem').map((item) => item.textContent ?? '')
    expect(labels).toHaveLength(3)
    for (const label of labels) {
      expect(label).not.toMatch(BANNED_WORDS)
      expect(label).not.toMatch(CROSSING)
      expect(label).not.toMatch(NINE_LEVELS)
      expect(label).not.toMatch(WHOLE_ROAD)
      expect(label).not.toMatch(APPROACH)
    }
  })
})

describe('Details', () => {
  it('opens to the reason code and the photo\'s time, and shows no report id, no URL and no error text', async () => {
    const result = await takePhoto('refused_too_dark')
    const { container } = renderCard({ result })
    const details = container.querySelector('details') as HTMLDetailsElement
    expect(details.open).toBe(false)

    fireEvent.click(within(details).getByText('Details'))
    expect(details.open).toBe(true)

    expect(within(details).getByText('Reason code: too_dark')).toBeTruthy()
    expect(within(details).getByText(/^Photo time: Oct 30, 2026, 6:19\sPM GMT\+8$/)).toBeTruthy()
    // The SVG icons carry the W3C namespace; no other address is on the card but the two official sites.
    const everything = (container.innerHTML + text()).replaceAll('http://www.w3.org/2000/svg', '')
    expect(everything).not.toMatch(/r_[0-9a-f]{32}/)
    expect(everything).not.toContain(result.reportId)
    expect(everything).not.toMatch(/https?:\/\/(?!mmda\.gov\.ph|www\.pagasa)/)
    expect(everything).not.toMatch(/HTTP \d|\[object|undefined|NaN/)
  })

  it('shows only the time on a level result, and only the code on a sample, whose photo time is not the run\'s', async () => {
    renderCard({ result: await takePhoto() })
    const level = screen.getByText('Details').closest('details') as HTMLElement
    expect(within(level).queryByText(/Reason code/)).toBeNull()
    expect(within(level).getByText(/Photo time:/)).toBeTruthy()
    cleanup()

    const refused: ReportResult = {
      reportId: '',
      status: 'refused',
      refusalReason: 'water_unsure',
      mode: 'sample',
      published: false,
      capturedAt: '2026-10-30T10:19:00Z',
    }
    renderCard({ result: refused, source: 'sample' })
    const sample = screen.getByText('Details').closest('details') as HTMLElement
    expect(within(sample).getByText('Reason code: water_unsure')).toBeTruthy()
    expect(within(sample).queryByText(/Photo time/)).toBeNull()
  })

  it('leaves out a reason that is not a plain code, so no error text, address or id can reach the screen', async () => {
    const result = await takePhoto('refused_too_dark')
    for (const reason of ['Error: connection reset at https://example.invalid/x', `failed for ${result.reportId}`, '', 'Too_Dark']) {
      const { container } = renderCard({ result: { ...result, refusalReason: reason } })
      fireEvent.click(screen.getByText('Details'))
      expect(container.textContent, reason).not.toContain('Reason code')
      expect(container.textContent, reason).not.toContain('example.invalid')
      expect(container.textContent, reason).not.toContain(result.reportId)
      cleanup()
    }
  })

  it('has none when it has nothing to show', () => {
    const { container } = renderCard({ result: pinAt('knee', { capturedAt: 'later' }), source: 'pin' })
    expect(container.querySelector('details')).toBeNull()
  })
})

describe('dropped references', () => {
  it('shows a dropped reference\'s cause and no level, and accepts its null level and null inches', async () => {
    const result = await takePhoto()
    const dropped = (result.readings ?? []).find((reading) => reading.dropped !== null)
    expect(dropped).toMatchObject({ id: 3, level: null, inches: null, dropped: 'person_not_adult' })
    const { container } = renderCard({ result })

    const list = container.querySelector('details') as HTMLElement
    fireEvent.click(within(list).getByText('Details'))
    const item = within(list).getByText(/^Reference 3:/).closest('li') as HTMLElement
    expect(item.textContent).toBe('Reference 3: Not used, since this person may not be an adult.')
    expect(item.textContent).not.toMatch(/deep|MMDA|level|null|NaN|undefined|person_not_adult/)
    // The two used references say where the water meets them.
    expect(within(list).getByText(/^Reference 1:/).closest('li')?.textContent).toContain('three quarters')
    expect(within(list).getByText(/^Reference 2:/).closest('li')?.textContent).toContain('knees of an adult')
  })

  it('never shows a cause it has no line for as a code', async () => {
    const result = await takePhoto()
    const readings = (result.readings ?? []).map((reading) =>
      reading.dropped === null ? reading : { ...reading, dropped: 'a_cause_from_a_newer_pipeline' },
    )
    const { container } = renderCard({ result: { ...result, readings } })
    expect(container.textContent).toContain('Reference 3: Not used for this reading.')
    expect(container.textContent).not.toContain('a_cause_from_a_newer_pipeline')
  })

  it('shows no list for a result that has no readings, as a pin or a saved sample has', () => {
    const { container } = renderCard({ result: pinAt('knee'), source: 'pin' })
    expect(container.textContent).not.toMatch(/Reference \d/)
  })
})

describe('in Taglish', () => {
  it('shows a refused card\'s reason line and D19\'s line in Taglish, unmarked, now that the M20 review has passed them', async () => {
    renderCard({ result: await takePhoto('refused_too_dark') }, 'fil')
    const reason = screen.getByText(FIL['reason.too_dark'].text)
    expect(FIL['reason.too_dark'].reviewed).toBe(true)
    expect(reason.getAttribute('lang')).toBeNull()
    expect(reason.tagName).toBe('P')
    expect(screen.getByText(FIL['refusal.d19'].text).closest('[lang="en"]')).toBeNull()
    expect(screen.queryByText(D19)).toBeNull()
  })

  it('shows a refusal line whose Taglish is not reviewed in English inside an element marked lang="en"', async () => {
    const reason = FIL['reason.too_dark']
    const d19 = FIL['refusal.d19']
    FIL['reason.too_dark'] = { ...reason, reviewed: false }
    FIL['refusal.d19'] = { ...d19, reviewed: false }
    try {
      renderCard({ result: await takePhoto('refused_too_dark') }, 'fil')
      const line = screen.getByText('The photo is too dark to read.')
      expect(line.getAttribute('lang')).toBe('en')
      expect(line.tagName).toBe('SPAN')
      expect(screen.getByText(D19).getAttribute('lang')).toBe('en')
    } finally {
      FIL['reason.too_dark'] = reason
      FIL['refusal.d19'] = d19
    }
  })

  it('shows the frame\'s two lines in Taglish, unmarked, now that they are reviewed', async () => {
    const refused: ReportResult = {
      reportId: '',
      status: 'refused',
      refusalReason: 'water_unsure',
      mode: 'sample',
      published: false,
    }
    renderCard({ result: refused, source: 'sample' }, 'fil')
    for (const key of ['refusal.sample.cantTell', 'refusal.sample.someoneWouldSee'] as const) {
      expect(FIL[key].reviewed, key).toBe(true)
      const line = screen.getByText(FIL[key].text)
      expect(line.closest('[lang="en"]'), key).toBeNull()
    }
    expect(screen.queryByText("Lusot can't tell from this photo.")).toBeNull()
  })

  it('words a level result in Taglish, with the level line in Taglish', async () => {
    renderCard({ result: await takePhoto() }, 'fil')
    expect(screen.getByText('Knee ang lalim sa spot na ito (MMDA level).')).toBeTruthy()
    expect(screen.getByText('Mula sa 2 reference object.')).toBeTruthy()
    expect(screen.getByText(/^Kinunan ang photo .* Nasa loob ng 12 m ang lokasyon\.$/)).toBeTruthy()
  })

  it('words "failed" and "no flood seen" in Taglish, apart from each other', async () => {
    renderCard({ result: await takePhoto('failed_model_error'), onNewPhoto: vi.fn() }, 'fil')
    expect(screen.getByText('Nabigo ang pagproseso, subukan ulit.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Subukan ulit' })).toBeTruthy()
    cleanup()
    renderCard({ result: await takePhoto('no_flood_seen') }, 'fil')
    expect(screen.getByText('Walang bahang nakita sa spot na ito.')).toBeTruthy()
  })
})

// The next-step tips under a refusal (the refusal-tips proposal, approved at M20 on Nov 1): five reasons have one,
// shown under the reason line on your own refusal only, never on a photo the person didn't take (C637).
describe('the next-step tip under a refusal', () => {
  const TIPPED = ['no_usable_reference', 'photo_unusable', 'water_unsure', 'no_water_found', 'references_disagree'] as const
  const TABLE = { en: EN, fil: FIL }
  const allTips = () => TIPPED.flatMap((reason) => [EN[`tip.${reason}`].text, FIL[`tip.${reason}`].text])

  it("shows your own refusal's tip after D19's line and the reason line, in English and in reviewed Taglish", async () => {
    for (const reason of TIPPED) {
      const result = await takePhoto(`refused_${reason}`)
      for (const lang of ['en', 'fil'] as const) {
        renderCard({ result }, lang)
        const d19 = screen.getByText(TABLE[lang]['refusal.d19'].text)
        const why = screen.getByText(TABLE[lang][`reason.${reason}`].text)
        const tip = screen.getByText(TABLE[lang][`tip.${reason}`].text)
        expect(d19.compareDocumentPosition(why) & Node.DOCUMENT_POSITION_FOLLOWING, `${reason} ${lang}`).toBeTruthy()
        expect(why.compareDocumentPosition(tip) & Node.DOCUMENT_POSITION_FOLLOWING, `${reason} ${lang}`).toBeTruthy()
        expect(TABLE[lang][`tip.${reason}`].reviewed, `${reason} ${lang}`).toBe(true)
        // A Taglish tip isn't an English fallback (C619).
        if (lang === 'fil') expect(tip.closest('[lang="en"]'), reason).toBeNull()
        cleanup()
        localStorage.clear()
      }
    }
  })

  it('shows no tip for a refusal reason that has none', async () => {
    const untipped = REFUSED_REASONS.filter((reason) => !(TIPPED as readonly string[]).includes(reason))
    expect(untipped.length).toBeGreaterThan(0)
    for (const reason of untipped) {
      renderCard({ result: await takePhoto(`refused_${reason}`) })
      for (const tip of allTips()) expect(text(), reason).not.toContain(tip)
      cleanup()
    }
  })

  it("shows no tip on a saved sample's refusal or a demo report's refusal", () => {
    const sample: ReportResult = {
      reportId: '',
      status: 'refused',
      refusalReason: 'no_usable_reference',
      mode: 'sample',
      published: false,
    }
    renderCard({ result: sample, source: 'sample', savedAt: '2026-10-29T14:20:00Z' })
    expect(screen.getByText(EN['reason.no_usable_reference'].text)).toBeTruthy()
    for (const tip of allTips()) expect(text()).not.toContain(tip)
    cleanup()

    renderCard({ result: { ...sample, mode: 'demo', published: true } })
    expect(screen.getByText(EN['reason.no_usable_reference'].text)).toBeTruthy()
    for (const tip of allTips()) expect(text()).not.toContain(tip)
  })

  it("shows no tip on someone else's refused report opened from the map, or on a failure that carries a refusal code", () => {
    const theirs: ReportResult = {
      reportId: 'r',
      status: 'refused',
      refusalReason: 'water_unsure',
      mode: 'live',
      published: true,
    }
    renderCard({ result: theirs, source: 'pin' })
    expect(screen.getByText(EN['reason.water_unsure'].text)).toBeTruthy()
    for (const tip of allTips()) expect(text()).not.toContain(tip)
    cleanup()

    // Tips belong to "can't tell" only: "processing failed" stays its own outcome.
    renderCard({ result: { ...theirs, status: 'failed', refusalReason: 'photo_unusable', published: false } })
    expect(screen.getByRole('status').textContent).toContain('Processing failed, try again.')
    for (const tip of allTips()) expect(text()).not.toContain(tip)
  })

  it('shows a tip whose Taglish is not reviewed in English inside an element marked lang="en"', async () => {
    const tip = FIL['tip.no_water_found']
    FIL['tip.no_water_found'] = { ...tip, reviewed: false }
    try {
      renderCard({ result: await takePhoto('refused_no_water_found') }, 'fil')
      expect(screen.getByText(EN['tip.no_water_found'].text).getAttribute('lang')).toBe('en')
      expect(screen.queryByText(tip.text)).toBeNull()
    } finally {
      FIL['tip.no_water_found'] = tip
    }
  })

  // The approved words, pinned the way D19's line is, so that any edit (a dropped "without" or "hindi") fails here
  // and goes back to Rene's review.
  it('keeps the approved words exactly', () => {
    const APPROVED: Record<(typeof TIPPED)[number], { en: string; fil: string }> = {
      no_usable_reference: {
        en: 'Photograph the spot itself, not a picture on a screen. Lusot can read the depth from the wheel of a parked car, SUV or van that the water already reaches, not from a jeepney, bus, big truck, tricycle or motorcycle. From a dry sidewalk, without going nearer the water, retake with one such wheel large and clear in the photo.',
        fil: 'Kunan ang mismong spot, hindi ang larawan sa screen. Mababasa ng Lusot ang lalim mula sa gulong ng nakaparadang kotse, SUV o van na inaabot na ng tubig, hindi mula sa jeepney, bus, malaking truck, tricycle o motorsiklo. Mula sa tuyong bangketa, nang hindi lumalapit sa tubig, kunan ulit nang malaki at malinaw sa photo ang isang ganoong gulong.',
      },
      photo_unusable: {
        en: 'Photograph the spot itself, not a picture on a screen. Lusot needs a clear view of this spot: wipe the lens, hold the phone still, and retake from a dry sidewalk with nothing in front of the camera.',
        fil: 'Kunan ang mismong spot, hindi ang larawan sa screen. Kailangan ng Lusot ng malinaw na kita ng spot na ito: punasan ang lens, hawakan nang steady ang phone, at kunan ulit mula sa tuyong bangketa nang walang nakaharang sa camera.',
      },
      water_unsure: {
        en: "Lusot couldn't tell floodwater from wet ground. From a dry sidewalk, retake with the water clearly in view where it meets a parked car's wheel.",
        fil: 'Hindi masabi ng Lusot kung baha ito o basa lang ang lupa. Mula sa tuyong bangketa, kunan ulit nang malinaw na kita ang tubig kung saan ito dumidikit sa gulong ng isang nakaparadang kotse.',
      },
      no_water_found: {
        en: "From a dry sidewalk, without going nearer the water, retake with more of the water's surface in the photo, so its edge around a parked car's wheel shows clearly.",
        fil: 'Mula sa tuyong bangketa, nang hindi lumalapit sa tubig, kunan ulit nang mas malaki ang kita ng ibabaw ng tubig sa photo, para malinaw ang gilid nito sa paligid ng gulong ng isang nakaparadang kotse.',
      },
      references_disagree: {
        en: "Cars or people at different depths can mean the water is uneven here. Lusot won't pick one depth over another, so it gives no level for this photo.",
        fil: 'Kapag magkakaiba ang lalim sa mga kotse o tao, puwedeng hindi pantay ang tubig dito. Hindi pipili ang Lusot ng isang lalim kaysa sa iba, kaya walang level para sa photo na ito.',
      },
    }
    for (const reason of TIPPED) {
      expect(EN[`tip.${reason}`], reason).toEqual({ text: APPROVED[reason].en, reviewed: true })
      expect(FIL[`tip.${reason}`], reason).toEqual({ text: APPROVED[reason].fil, reviewed: true })
    }
  })

  it('words each tip within the copy rules: no banned word, crossing phrase, whole road or approach, and every retake from a dry sidewalk', () => {
    for (const reason of TIPPED) {
      for (const lang of ['en', 'fil'] as const) {
        const tip = TABLE[lang][`tip.${reason}`].text
        expect(tip, `${reason} ${lang}`).not.toMatch(BANNED_WORDS)
        expect(tip, `${reason} ${lang}`).not.toMatch(CROSSING)
        expect(tip, `${reason} ${lang}`).not.toMatch(NINE_LEVELS)
        expect(tip, `${reason} ${lang}`).not.toMatch(WHOLE_ROAD)
        expect(tip, `${reason} ${lang}`).not.toMatch(APPROACH)
        // The disagreement tip explains the refusal and asks for no retake (W10); the others retake from a dry sidewalk.
        if (reason !== 'references_disagree') {
          expect(tip, `${reason} ${lang}`).toMatch(lang === 'en' ? /from a dry sidewalk/i : /mula sa tuyong bangketa/i)
        } else {
          expect(tip, `${reason} ${lang}`).not.toMatch(/retake|kunan ulit/i)
        }
      }
    }
  })
})

describe('the words on the card', () => {
  const SCENARIOS = scenarioNames().filter((name) => /^(level_|no_flood|refused_|failed_)/.test(name))

  it('finds every outcome the mock can give', () => {
    expect(SCENARIOS).toHaveLength(6 + 1 + 8 + 6)
  })

  it('never matches the banned words, a crossing phrase or "MMDA\'s 9 levels", in either language, on any card', async () => {
    for (const scenario of SCENARIOS) {
      const result = await takePhoto(scenario)
      for (const lang of ['en', 'fil'] as const) {
        const { container } = renderCard({ result, onNewPhoto: vi.fn(), onCheckAgain: vi.fn() }, lang)
        fireEvent.click(screen.getByText(lang === 'en' ? 'Details' : 'Mga detalye'))
        const shown = container.textContent ?? ''
        expect(shown, `${scenario} ${lang}`).not.toMatch(BANNED_WORDS)
        expect(shown, `${scenario} ${lang}`).not.toMatch(CROSSING)
        expect(shown, `${scenario} ${lang}`).not.toMatch(NINE_LEVELS)
        // D19 tells people what not to do near water and the road, so a refusal is the one card allowed to say so.
        if (!scenario.startsWith('refused_')) {
          expect(shown, `${scenario} ${lang}`).not.toMatch(WHOLE_ROAD)
          expect(shown, `${scenario} ${lang}`).not.toMatch(APPROACH)
        }
        expect(shown, `${scenario} ${lang}`).not.toMatch(/undefined|NaN|\[object|null\b/)
        cleanup()
        localStorage.clear()
      }
    }
  })

  it('never matches them on a sample, a demo pin, a saved result or a paused notice either', async () => {
    const { fetchFn, c } = mockWith()
    const samples = await getSamples(API, fetchFn)
    const started = (await runSample(API, samples[0].sampleId, DEVICE, fetchFn)) as { reportId: string }
    const result = await pollReport(API, started.reportId, { fetchFn, sleep: c.sleep, now: c.now })
    const demo = (await getPins(API, fetchFn)).find((pin) => pin.mode === 'demo') as Pin
    // What a sample run answers while analysis is paused (amendment 10): a level, no basis, inches or readings.
    const saved: ReportResult = {
      reportId: '',
      status: 'done',
      mode: 'sample',
      published: false,
      noFloodSeen: false,
      level: 'knee',
      landmark: 'rim_three_quarters',
      passability: 'NPLV',
      levelIsFloor: false,
    }
    const cards: Props[] = [
      { result, source: 'sample', sample: samples[0] },
      { result: demo, source: 'pin' },
      { result: saved, source: 'sample', sample: samples[0], savedAt: '2026-10-29T14:20:00Z' },
      { result: await takePhoto('failed_model_calls_paused') },
    ]
    for (const props of cards) {
      for (const lang of ['en', 'fil'] as const) {
        renderCard(props, lang)
        const shown = text()
        expect(shown).not.toMatch(BANNED_WORDS)
        expect(shown).not.toMatch(CROSSING)
        expect(shown).not.toMatch(NINE_LEVELS)
        expect(shown).not.toMatch(WHOLE_ROAD)
        expect(shown).not.toMatch(APPROACH)
        cleanup()
        localStorage.clear()
      }
    }
  })
})
