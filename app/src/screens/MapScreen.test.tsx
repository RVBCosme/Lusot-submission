import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import L from 'leaflet'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../i18n'
import { EN, type StringKey } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { Layout } from '../layout/Layout'
import { getPins, getReport, type Pin } from '../lib/api'
import { LocationDenied, locateOnce } from '../lib/geo'
import { writeItem } from '../lib/storage'
import { flagCount, resetPinMemory } from '../map/pins'
import { createMockFetch } from '../mock/mockFetch'
import type { Scenario } from '../mock/fixtures'
import type { OwnPin } from '../report/flow'
import { deferred } from '../test/camera'
import { MapScreen } from './MapScreen'

// The app's fetch, swapped per test for Task 6's mock API or a scripted answer.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))
// The calls the map makes, watched, and answered by the real client behind them.
vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return { ...actual, getPins: vi.fn(actual.getPins), getReport: vi.fn(actual.getReport) }
})
// One position, answered by hand.
vi.mock('../lib/geo', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/geo')>()),
  locateOnce: vi.fn(),
}))
// The person's own pin and the function that tells the flow what the map holds (Task 12's provider is not needed).
const flow = vi.hoisted(() => ({ pin: undefined as unknown, seen: undefined as unknown }))
vi.mock('../report/ReportFlowProvider', () => ({
  useOwnPin: () => flow.pin,
  useSeenOnMap: () => flow.seen,
}))

const API = 'https://api.example.test'
const T0 = Date.parse('2026-10-30T09:15:30.000Z')
const MIN = 60_000
const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
// Task 6's seeded pins: A 10 min, B 25 min (2 flags), C 90 min (faded floor), D 200 min (past 3 hours), E a demo
// photo from 2009, F a level the app can't word (dropped by the client).
const A = 'r_1a2b3c4d5e6f40718293a4b5c6d7e8f9'
const B = 'r_2b3c4d5e6f7a41829304b5c6d7e8f9a0'
const C = 'r_3c4d5e6f7a8b429304a5b6c7d8e9f0a1'
const E = 'r_5e6f7a8b9c0d44b506c7d8e9f0a1b2c3'
const ROW_A = 'Knee deep at this spot (MMDA level). Photo taken 10 min ago.'
const ROW_B = 'Half-tire deep at this spot (MMDA level). Photo taken 25 min ago.'
const ROW_C = 'At least tire deep at this spot (MMDA level). Photo taken 1 h 30 min ago.'
const ROW_E = 'Demo. Above chest deep at this spot. Photo from Sep 26, 2009'

const text = (key: StringKey) => EN[key].text
const ownPin: OwnPin = {
  id: 'r_aabbccddeeff00112233445566778899',
  lat: 14.6021,
  lng: 120.9988,
  capturedAt: '2026-10-30T09:12:30.345Z',
  mode: 'live',
  flags: 0,
  gpsAccuracyM: 12,
  level: 'knee',
  landmark: 'rim_three_quarters',
  passability: 'NPLV',
  levelIsFloor: false,
  basis: { vehicles: 1, people: 1 },
  own: true,
}

// ---- helpers ----

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })

function mockApi(scenario: Scenario = 'level_knee') {
  net.fetch = createMockFetch({ scenario, now: () => Date.now() })
}

// An API that gives `answers` to GET /map/pins in turn, repeating the last, and records its calls.
function scriptedPins(answers: (Pin[] | Error | Promise<Pin[]>)[]) {
  const urls: string[] = []
  let call = 0
  net.fetch = async (input) => {
    urls.push(String(input))
    const answer = answers[Math.min(call++, answers.length - 1)]
    if (answer instanceof Error) throw answer
    return json({ pins: await answer })
  }
  return urls
}

const pin = (over: Partial<Pin> & { id: string }): Pin => ({
  lat: 14.61,
  lng: 120.99,
  capturedAt: new Date(T0 - 5 * MIN).toISOString(),
  mode: 'live',
  flags: 0,
  gpsAccuracyM: 10,
  level: 'knee',
  landmark: 'rim_three_quarters',
  passability: 'NPLV',
  levelIsFloor: false,
  basis: { vehicles: 1, people: 0 },
  ...over,
})

const advance = async (ms: number) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}
const settle = () => advance(0)

function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state })
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'))
  })
}

let maps: L.Map[] = []
function renderMap({ apiUrl = API, lang = 'en', layout = false } = {}) {
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  const screenOnly = <MapScreen apiUrl={apiUrl} />
  const view = layout ? (
    <Layout route={{ name: 'map' }} apiReady={apiUrl !== ''}>
      {screenOnly}
    </Layout>
  ) : (
    <main>{screenOnly}</main>
  )
  return render(<LanguageProvider>{view}</LanguageProvider>)
}

async function open(options?: Parameters<typeof renderMap>[0]) {
  const view = renderMap(options)
  await settle()
  return view
}

const markers = () => [...document.querySelectorAll<HTMLElement>('.map-pin')]
const labels = () => markers().map((marker) => marker.getAttribute('aria-label'))
const rows = () =>
  within(screen.getByRole('list', { name: /^(Reports, newest first|Mga report, pinakabago muna)$/ })).getAllByRole('listitem')
// A row's lines: the level line, then the age or the photo's date.
const rowLines = (row: HTMLElement) => [...row.querySelectorAll('[data-line]')].map((line) => line.textContent)
const showList = () => fireEvent.click(screen.getByRole('button', { name: /^(List|Listahan)$/ }))
const showMap = () => fireEvent.click(screen.getByRole('button', { name: text('nav.map') }))
const locateButton = () => screen.getByRole('button', { name: text('map.locate') })

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] })
  vi.setSystemTime(T0)
  vi.mocked(getPins).mockClear()
  vi.mocked(getReport).mockClear()
  vi.mocked(locateOnce).mockReset()
  flow.pin = undefined
  flow.seen = vi.fn()
  resetPinMemory()
  maps = []
  const makeMap = L.map as unknown as (...args: unknown[]) => L.Map
  vi.spyOn(L, 'map').mockImplementation(((...args: unknown[]) => {
    const made = makeMap(...args)
    maps.push(made)
    return made
  }) as never)
  mockApi()
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' })
  localStorage.clear()
  sessionStorage.clear()
  history.replaceState(null, '', '/')
  document.documentElement.removeAttribute('lang')
})

// ---- the refresh ----

describe('the refresh', () => {
  it('calls getPins(apiUrl) on open, again after 60,000 ms, and again 60,000 ms after that', async () => {
    await open()
    expect(getPins).toHaveBeenCalledExactlyOnceWith(API)

    await advance(59_999)
    expect(getPins).toHaveBeenCalledTimes(1)
    await advance(1)
    expect(getPins).toHaveBeenCalledTimes(2)
    await advance(60_000)
    expect(getPins).toHaveBeenCalledTimes(3)
  })

  it('does not read while the page is hidden, and reads at once when it becomes visible again, then every 60,000 ms', async () => {
    await open()
    setVisibility('hidden')
    await advance(300_000)
    expect(getPins).toHaveBeenCalledTimes(1)

    setVisibility('visible')
    await settle()
    expect(getPins).toHaveBeenCalledTimes(2)
    await advance(59_999)
    expect(getPins).toHaveBeenCalledTimes(2)
    await advance(1)
    expect(getPins).toHaveBeenCalledTimes(3)
  })

  it('reads nothing on a page that opens hidden, until it is shown', async () => {
    setVisibility('hidden')
    await open()
    await advance(120_000)
    expect(getPins).not.toHaveBeenCalled()

    setVisibility('visible')
    await settle()
    expect(getPins).toHaveBeenCalledTimes(1)
  })

  it('stops with the screen: no getPins after it unmounts, whether the page is shown or hidden or comes back', async () => {
    const { unmount } = await open()
    unmount()
    await advance(600_000)
    setVisibility('hidden')
    setVisibility('visible')
    await advance(600_000)
    expect(getPins).toHaveBeenCalledTimes(1)
  })

  it('drops a read that was answered after the screen went, and tells the flow nothing about it', async () => {
    const answer = deferred<Pin[]>()
    scriptedPins([answer.promise])
    const { unmount } = renderMap()
    await settle()
    unmount()
    answer.resolve([pin({ id: A })])
    await settle()
    expect(flow.seen).not.toHaveBeenCalled()
  })

  it('shows what the later read answered, even when an older read is answered after it', async () => {
    const slow = deferred<Pin[]>()
    scriptedPins([slow.promise, [pin({ id: B })]])
    await open()
    setVisibility('hidden')
    setVisibility('visible')
    await settle()
    expect(markers()).toHaveLength(1)

    slow.resolve([pin({ id: A }), pin({ id: C })])
    await settle()
    expect(markers()).toHaveLength(1)
  })

  it('feeds useSeenOnMap every list it gets, as the API gave it, and not the own pin', async () => {
    flow.pin = ownPin
    scriptedPins([[pin({ id: A })], [pin({ id: A }), pin({ id: B })]])
    await open()
    expect(flow.seen).toHaveBeenNthCalledWith(1, [expect.objectContaining({ id: A })])
    await advance(60_000)
    expect(flow.seen).toHaveBeenCalledTimes(2)
    expect(vi.mocked(flow.seen as ReturnType<typeof vi.fn>).mock.calls[1]?.[0]).toHaveLength(2)
  })

  it('records the flag count of every pin it reads, so pin detail never shows one lower than the map did', async () => {
    scriptedPins([[pin({ id: A, flags: 5 })], [pin({ id: A, flags: 1 })]])
    await open()
    await advance(60_000)
    expect(flagCount(A, 0)).toBe(5)
  })

  it('without an API address, makes no read and starts no timer, and says so plainly without an alert', async () => {
    await open({ apiUrl: '' })
    await advance(300_000)
    expect(getPins).not.toHaveBeenCalled()
    expect(screen.getByText(text('map.noApi'))).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByText(text('map.empty.title'))).toBeNull()
    expect(document.querySelector('.leaflet-container')).not.toBeNull()
  })

  it('says it could not load, and not "no reports", when the first read fails, and carries on', async () => {
    scriptedPins([new TypeError('network'), [pin({ id: A })]])
    await open()
    expect(screen.getByText(text('map.loadFailed'))).toBeTruthy()
    expect(screen.queryByText(text('map.empty.title'))).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()

    await advance(60_000)
    expect(screen.queryByText(text('map.loadFailed'))).toBeNull()
    expect(markers()).toHaveLength(1)
  })

  it('keeps the pins it has when a later read fails, and says so', async () => {
    scriptedPins([[pin({ id: A })], new TypeError('network')])
    await open()
    await advance(60_000)
    expect(markers()).toHaveLength(1)
    expect(screen.getByText(text('map.loadFailed'))).toBeTruthy()
  })

  it('says it is loading until the first read is answered, and shows no empty state meanwhile', async () => {
    const answer = deferred<Pin[]>()
    scriptedPins([answer.promise])
    renderMap()
    await settle()
    expect(screen.getByText(text('map.loading'))).toBeTruthy()
    expect(screen.queryByText(text('map.empty.title'))).toBeNull()

    answer.resolve([])
    await settle()
    expect(screen.queryByText(text('map.loading'))).toBeNull()
    expect(screen.getByText(text('map.empty.title'))).toBeTruthy()
  })
})

// ---- the map and its markers ----

describe('the markers', () => {
  it('draws the live and demo pins, a faded one included, and not one past 3 hours or one the app cannot word', async () => {
    await open()
    expect(labels()).toEqual(expect.arrayContaining([ROW_A, ROW_B, ROW_C, ROW_E]))
    expect(markers()).toHaveLength(4)
  })

  it('makes each marker keyboard-reachable and labelled with the level line and age, and nothing else', async () => {
    await open()
    for (const marker of markers()) {
      expect(marker.getAttribute('role')).toBe('button')
      expect(marker.getAttribute('tabindex')).toBe('0')
      expect(marker.getAttribute('aria-label')).toMatch(/at this spot/)
    }
    const visible = [document.body.textContent, ...labels(), document.body.innerHTML].join('\n')
    expect(visible).not.toMatch(/r_[0-9a-f]{32}/)
    expect(labels().join('')).not.toMatch(/14\.6|120\.9|121\.0/)
  })

  it('shows a floor reading as a floor, a demo pin as Demo with its photo date, and no accuracy or place on either', async () => {
    await open()
    expect(labels()).toContain(ROW_C)
    expect(labels()).toContain(ROW_E)
    expect(labels().join('\n')).not.toMatch(/Marikina|Ondoy|within \d+ m/)
  })

  it('opens pin detail for a pin, by a click, Enter or Space, and never from anything but a pin it read', async () => {
    await open()
    const [first] = markers().filter((marker) => marker.getAttribute('aria-label') === ROW_A)
    expect(first).toBeDefined()
    fireEvent.click(first as HTMLElement)
    expect(window.location.hash).toBe(`#/pin/${A}`)

    window.location.hash = ''
    fireEvent.keyDown(first as HTMLElement, { key: 'Enter' })
    expect(window.location.hash).toBe(`#/pin/${A}`)

    window.location.hash = ''
    const space = fireEvent.keyDown(first as HTMLElement, { key: ' ' })
    expect(window.location.hash).toBe(`#/pin/${A}`)
    expect(space).toBe(false) // the page doesn't scroll
  })

  it('does not open anything for another key', async () => {
    await open()
    fireEvent.keyDown(markers()[0] as HTMLElement, { key: 'a' })
    expect(window.location.hash).toBe('')
  })

  it('marks a live pin full for its first hour and faded after it, and a demo pin never faded', async () => {
    await open()
    const byLabel = (label: string) => markers().find((marker) => marker.getAttribute('aria-label') === label)
    expect(byLabel(ROW_A)?.classList.contains('map-pin-faded')).toBe(false)
    expect(byLabel(ROW_C)?.classList.contains('map-pin-faded')).toBe(true)
    expect(byLabel(ROW_E)?.classList.contains('map-pin-faded')).toBe(false)
    expect(byLabel(ROW_E)?.classList.contains('map-pin-demo')).toBe(true)
    expect(byLabel(ROW_A)?.classList.contains('map-pin-demo')).toBe(false)
  })

  it('fades a pin as the hour passes, and drops one at 3 hours, with no new read to say so', async () => {
    const at = (minutes: number) => new Date(T0 - minutes * MIN).toISOString()
    scriptedPins([[pin({ id: A, capturedAt: at(59.5) }), pin({ id: B, capturedAt: at(179.5) })]])
    await open()
    const [first, second] = markers() as [HTMLElement, HTMLElement]
    expect(markers().map((marker) => marker.classList.contains('map-pin-faded'))).toEqual([false, true])

    await advance(60_000)
    expect(markers()).toHaveLength(1)
    expect(second.isConnected).toBe(false)
    expect(first.classList.contains('map-pin-faded')).toBe(true)
  })

  it('keeps each marker element across a refresh, and gives it its new age: a focused marker is not lost', async () => {
    await open()
    const before = markers().find((marker) => marker.getAttribute('aria-label') === ROW_A) as HTMLElement
    before.focus()
    await advance(60_000)

    const after = markers().find((marker) => marker.getAttribute('aria-label')?.startsWith('Knee deep'))
    expect(after).toBe(before)
    expect(after?.getAttribute('aria-label')).toBe('Knee deep at this spot (MMDA level). Photo taken 11 min ago.')
    expect(document.activeElement).toBe(before)
  })

  it('takes a pin off the map when a read no longer holds it', async () => {
    scriptedPins([[pin({ id: A }), pin({ id: B })], [pin({ id: B })]])
    await open()
    expect(markers()).toHaveLength(2)
    await advance(60_000)
    expect(markers()).toHaveLength(1)
  })

  it('gives the map, its zoom buttons and its credit a name in the page language', async () => {
    await open({ lang: 'fil' })
    expect(screen.getByRole('group', { name: FIL['map.mapLabel'].text })).toBeTruthy()
    expect(screen.getByRole('button', { name: FIL['map.zoomIn'].text })).toBeTruthy()
    expect(screen.getByRole('button', { name: FIL['map.zoomOut'].text })).toBeTruthy()
  })

  it('removes the map, with its markers, when the screen goes', async () => {
    const { unmount } = await open()
    expect(document.querySelector('.leaflet-container')).not.toBeNull()
    unmount()
    expect(document.querySelector('.leaflet-container')).toBeNull()
  })
})

describe('the credit', () => {
  it('links "© OpenStreetMap contributors" to the copyright page, in the screen and above the screen-line bar', async () => {
    await open({ layout: true })
    const link = screen.getByRole('link', { name: '© OpenStreetMap contributors' })
    expect(link.getAttribute('href')).toBe('https://www.openstreetmap.org/copyright')
    expect(screen.getByRole('main').contains(link)).toBe(true)
    const line = screen.getByText(SCREEN_LINE)
    expect(line.closest('footer')?.contains(link)).toBe(false)
    expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
  })
})

// ---- the list ----

describe('the list', () => {
  it('shows the same pins newest first, each with its level line and age, and a floor as a floor', async () => {
    await open()
    showList()
    expect(rows().map(rowLines)).toEqual([
      ['Knee deep at this spot (MMDA level).', 'Photo taken 10 min ago.'],
      ['Half-tire deep at this spot (MMDA level).', 'Photo taken 25 min ago.'],
      ['At least tire deep at this spot (MMDA level).', 'Photo taken 1 h 30 min ago.'],
      ['Above chest deep at this spot.', 'Photo from Sep 26, 2009'],
    ])
  })

  it('opens pin detail from a row, by a link to the pin, and marks a demo row as Demo', async () => {
    await open()
    showList()
    const links = rows().map((row) => within(row).getByRole('link'))
    expect(links.map((link) => link.getAttribute('href'))).toEqual([A, B, C, E].map((id) => `#/pin/${id}`))
    expect(within(rows()[3] as HTMLElement).getByText('Demo')).toBeTruthy()
    expect(within(rows()[0] as HTMLElement).queryByText('Demo')).toBeNull()
  })

  it('shows a Taglish screen the Taglish lines, and an ID or position nowhere', async () => {
    await open({ lang: 'fil' })
    showList()
    expect(screen.getByRole('list', { name: FIL['map.listLabel'].text })).toBeTruthy()
    expect(rows()[0]?.textContent).toContain('sa spot na ito')
    expect(document.body.textContent).not.toMatch(/r_[0-9a-f]{32}/)
  })

  it('goes back to the map, which stayed as it was', async () => {
    await open()
    const map = maps[0] as L.Map
    showList()
    expect(screen.queryByRole('group', { name: text('map.mapLabel') })).toBeNull()
    showMap()
    expect(screen.getByRole('group', { name: text('map.mapLabel') })).toBeTruthy()
    expect(maps).toHaveLength(1)
    expect(document.querySelector('.leaflet-container')).toBe(map.getContainer())
  })

  it('tells the view in use by aria-pressed on its two buttons', async () => {
    await open()
    const map = screen.getByRole('button', { name: text('nav.map') })
    const list = screen.getByRole('button', { name: text('map.list') })
    expect([map.getAttribute('aria-pressed'), list.getAttribute('aria-pressed')]).toEqual(['true', 'false'])
    showList()
    expect([map.getAttribute('aria-pressed'), list.getAttribute('aria-pressed')]).toEqual(['false', 'true'])
  })

  it('offers a link to Report, and none without an API address', async () => {
    await open()
    expect(screen.getByRole('link', { name: text('map.report') }).getAttribute('href')).toBe('#/report')
    cleanup()
    await open({ apiUrl: '' })
    expect(screen.queryByRole('link', { name: text('map.report') })).toBeNull()
  })
})

// ---- the own pin ----

describe('the own pin', () => {
  it('shows at once with the pins read, labelled as the person\'s own, and in the list', async () => {
    flow.pin = ownPin
    await open()
    expect(markers()).toHaveLength(5)
    expect(labels()).toContain('Your report. Knee deep at this spot (MMDA level). Photo taken 2 min ago.')
    showList()
    expect(rowLines(rows()[0] as HTMLElement)).toEqual(['Knee deep at this spot (MMDA level).', 'Photo taken 2 min ago.'])
    expect(within(rows()[0] as HTMLElement).getByText(text('map.own'))).toBeTruthy()
  })

  it('gives way to the API copy once the pins hold its id, and to a copy at the same second within 15 m', async () => {
    flow.pin = ownPin
    scriptedPins([[pin({ id: ownPin.id, lat: 14.9, lng: 121.5 })]])
    await open()
    expect(markers()).toHaveLength(1)
    expect(labels()[0]).not.toMatch(/Your report/)

    cleanup()
    scriptedPins([[pin({ id: 'r_x', lat: ownPin.lat + 0.0001, lng: ownPin.lng, capturedAt: '2026-10-30T09:12:30Z' })]])
    await open()
    expect(markers()).toHaveLength(1)
    expect(labels()[0]).not.toMatch(/Your report/)
  })

  it('opens the person\'s own result when tapped, from its own fields: no pin detail, and no call to GET /reports', async () => {
    flow.pin = ownPin
    await open()
    const mine = markers().find((marker) => marker.getAttribute('aria-label')?.startsWith('Your report'))
    fireEvent.click(mine as HTMLElement)
    await settle()

    expect(window.location.hash).toBe('')
    expect(getReport).not.toHaveBeenCalled()
    const card = screen.getByRole('article')
    expect(card.getAttribute('data-outcome')).toBe('level')
    expect(within(card).getByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 2, name: text('map.own') })).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 2 }))

    fireEvent.click(screen.getByRole('button', { name: text('map.back') }))
    expect(screen.queryByRole('article')).toBeNull()
    expect(screen.getByRole('group', { name: text('map.mapLabel') })).toBeTruthy()
  })

  it('opens the own result from the list too', async () => {
    flow.pin = ownPin
    await open()
    showList()
    fireEvent.click(within(rows()[0] as HTMLElement).getByRole('button'))
    expect(screen.getByRole('article').getAttribute('data-outcome')).toBe('level')
    expect(window.location.hash).toBe('')
  })

  it('falls back to the map when the own pin clears while its result is open', async () => {
    flow.pin = ownPin
    const view = await open()
    fireEvent.click(markers().find((marker) => marker.getAttribute('aria-label')?.startsWith('Your report')) as HTMLElement)
    expect(screen.getByRole('article')).toBeTruthy()

    flow.pin = undefined
    view.rerender(
      <LanguageProvider>
        <main>
          <MapScreen apiUrl={API} />
        </main>
      </LanguageProvider>,
    )
    expect(screen.queryByRole('article')).toBeNull()
    expect(screen.getByRole('group', { name: text('map.mapLabel') })).toBeTruthy()
  })
})

// ---- Locate me ----

describe('Locate me', () => {
  it('asks for one position and centres the map on it, with no pin and no upload', async () => {
    vi.mocked(locateOnce).mockResolvedValue({ lat: 14.5547, lng: 121.0244 })
    await open()
    const pinsBefore = markers().length
    const callsBefore = vi.mocked(getPins).mock.calls.length
    fireEvent.click(locateButton())
    await settle()

    expect(locateOnce).toHaveBeenCalledTimes(1)
    const centre = (maps[0] as L.Map).getCenter()
    expect(centre.lat).toBeCloseTo(14.5547, 4)
    expect(centre.lng).toBeCloseTo(121.0244, 4)
    expect(markers()).toHaveLength(pinsBefore)
    expect(vi.mocked(getPins).mock.calls).toHaveLength(callsBefore)
    expect(window.location.hash).toBe('')
  })

  it('zooms in to street level, and keeps a closer zoom as it is', async () => {
    vi.mocked(locateOnce).mockResolvedValue({ lat: 14.5547, lng: 121.0244 })
    await open()
    const map = maps[0] as L.Map
    fireEvent.click(locateButton())
    await settle()
    expect(map.getZoom()).toBe(16)

    map.setZoom(18)
    fireEvent.click(locateButton())
    await settle()
    expect(map.getZoom()).toBe(18)
  })

  it('shows no number and keeps nothing: nothing in the page, the storage or the console', async () => {
    const consoles = (['log', 'info', 'warn', 'error', 'debug'] as const).map((name) =>
      vi.spyOn(console, name).mockImplementation(() => {}),
    )
    vi.mocked(locateOnce).mockResolvedValue({ lat: 14.5547, lng: 121.0244 })
    await open()
    fireEvent.click(locateButton())
    await settle()

    expect(document.body.textContent).not.toMatch(/14\.5547|121\.0244|14\.55|121\.02/)
    expect(document.body.innerHTML).not.toMatch(/14\.5547|121\.0244/)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    for (const spy of consoles) expect(spy).not.toHaveBeenCalled()
  })

  it('asks once for two presses in the same moment', async () => {
    const answer = deferred<{ lat: number; lng: number }>()
    vi.mocked(locateOnce).mockReturnValue(answer.promise)
    await open()
    act(() => {
      locateButton().click()
      locateButton().click()
    })
    expect(locateOnce).toHaveBeenCalledTimes(1)
    answer.resolve({ lat: 14.55, lng: 121.02 })
    await settle()
    fireEvent.click(locateButton())
    expect(locateOnce).toHaveBeenCalledTimes(2)
  })

  it.each([
    ['a refusal', new LocationDenied('PERMISSION_DENIED'), 'location.denied'],
    ['location services off', new LocationDenied('OS-PLUG-GLOC-0007'), 'location.servicesOff'],
    ['any other error', new Error('boom'), 'location.unavailable'],
  ] as const)('%s shows its line and nothing else, and the map stays where it was', async (_name, error, line) => {
    vi.mocked(locateOnce).mockRejectedValue(error)
    await open()
    const before = (maps[0] as L.Map).getCenter()
    fireEvent.click(locateButton())
    await settle()

    const status = screen.getByText(text(line))
    expect(status.closest('[role="status"]')).not.toBeNull()
    expect((maps[0] as L.Map).getCenter()).toEqual(before)
    expect(document.body.textContent).not.toMatch(/boom/)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('clears the line on the next press, and says it is finding the spot while it waits', async () => {
    vi.mocked(locateOnce).mockRejectedValueOnce(new LocationDenied('PERMISSION_DENIED'))
    await open()
    fireEvent.click(locateButton())
    await settle()
    expect(screen.getByText(text('location.denied'))).toBeTruthy()

    const answer = deferred<{ lat: number; lng: number }>()
    vi.mocked(locateOnce).mockReturnValue(answer.promise)
    fireEvent.click(locateButton())
    await settle()
    expect(screen.queryByText(text('location.denied'))).toBeNull()
    expect(screen.getByText(text('report.locating'))).toBeTruthy()

    answer.resolve({ lat: 14.55, lng: 121.02 })
    await settle()
    expect(screen.queryByText(text('report.locating'))).toBeNull()
  })

  it('cancels its request when the screen goes, and does nothing with an answer that comes after', async () => {
    const answer = deferred<{ lat: number; lng: number }>()
    vi.mocked(locateOnce).mockReturnValue(answer.promise)
    const { unmount } = await open()
    const map = maps[0] as L.Map
    const setView = vi.spyOn(map, 'setView')
    fireEvent.click(locateButton())
    const signal = vi.mocked(locateOnce).mock.calls[0]?.[0]?.signal
    expect(signal?.aborted).toBe(false)

    unmount()
    expect(signal?.aborted).toBe(true)
    answer.resolve({ lat: 14.55, lng: 121.02 })
    await settle()
    expect(setView).not.toHaveBeenCalled()
  })
})

// ---- when there is nothing to show ----

describe('with no live and no demo pin', () => {
  beforeEach(() => mockApi('pins_none'))

  it('shows "No reports in the last 3 hours", "Try a sample" and one card marked as an example', async () => {
    await open()
    expect(screen.getByText(text('map.empty.title'))).toBeTruthy()
    expect(screen.getByRole('link', { name: text('map.trySample') }).getAttribute('href')).toBe('#/tested')
    const cards = screen.getAllByRole('article')
    expect(cards).toHaveLength(1)
    expect(within(cards[0] as HTMLElement).getByText(text('badge.example'))).toBeTruthy()
    expect(within(cards[0] as HTMLElement).getByText(text('map.example.note'))).toBeTruthy()
    expect(within(cards[0] as HTMLElement).getByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
  })

  it('never pins the example, and never says a place is dry or passable', async () => {
    await open()
    expect(markers()).toHaveLength(0)
    const words = [text('map.empty.title'), text('map.empty.note'), text('map.example.note')].join(' ')
    expect(words).not.toMatch(/\b(dry|clear|passable|no flood)\b/i)
    expect(screen.getByText(text('map.empty.note'))).toBeTruthy()
  })

  it('shows the same on the list view, and still one example', async () => {
    await open()
    showList()
    expect(screen.queryByRole('list', { name: text('map.listLabel') })).toBeNull()
    expect(screen.getByText(text('map.empty.title'))).toBeTruthy()
    expect(screen.getAllByRole('article')).toHaveLength(1)
  })

  it('does not show it when the person has a pin of their own', async () => {
    flow.pin = ownPin
    await open()
    expect(screen.queryByText(text('map.empty.title'))).toBeNull()
    expect(markers()).toHaveLength(1)
  })

  it('draws a pin that arrives on the next read, and takes the example away', async () => {
    scriptedPins([[], [pin({ id: A })]])
    await open()
    expect(screen.getByText(text('map.empty.title'))).toBeTruthy()
    await advance(60_000)
    expect(screen.queryByText(text('map.empty.title'))).toBeNull()
    expect(markers()).toHaveLength(1)
  })

  it('shows its Taglish lines in a Taglish screen', async () => {
    await open({ lang: 'fil' })
    expect(screen.getByText(FIL['map.empty.title'].text)).toBeTruthy()
    expect(screen.getByRole('link', { name: FIL['map.trySample'].text })).toBeTruthy()
  })
})

// ---- the words ----

const NEW_KEYS = (Object.keys(EN) as StringKey[]).filter(
  (key) => (/^(map|pin|flag)\./.test(key) && key !== 'pin.title') || key === 'badge.example',
)

describe('the new lines', () => {
  it('exist in both languages, start unreviewed, and keep to the product rules', () => {
    expect(NEW_KEYS.length).toBeGreaterThan(25)
    for (const key of NEW_KEYS) {
      for (const table of [EN, FIL]) {
        const { text: line, reviewed } = table[key]
        expect(line.length, key).toBeGreaterThan(2)
        expect(reviewed, key).toBe(false)
        expect(line, key).not.toMatch(/safe|ligtas/i)
        expect(line, key).not.toMatch(/you can cross|go ahead|pwedeng dumaan|tumawid ka|lusutan mo|you can pass|\bnine\b|9 levels/i)
        expect(line, key).not.toMatch(/\b(road|route|street|kalsada|daan|ruta)\b/i)
      }
    }
  })
})
