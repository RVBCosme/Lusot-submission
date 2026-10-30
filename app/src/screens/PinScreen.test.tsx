import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../i18n'
import { EN, type StringKey } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { flagPin, getReport, getPins, type Pin } from '../lib/api'
import { getDeviceId } from '../lib/device'
import { writeItem } from '../lib/storage'
import { flagCount, resetPinMemory, wasFlagged } from '../map/pins'
import { createMockFetch } from '../mock/mockFetch'
import type { Scenario } from '../mock/fixtures'
import { deferred } from '../test/camera'
import { polyfillDialog } from '../test/dialog'
import { PinScreen } from './PinScreen'

// The app's fetch, swapped per test for Task 6's mock API with a few answers of its own.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))
// The calls pin detail makes, watched, and answered by the real client behind them.
vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    getPins: vi.fn(actual.getPins),
    getReport: vi.fn(actual.getReport),
    flagPin: vi.fn(actual.flagPin),
  }
})
// What the flow is told about each list of pins (Task 12's provider is not needed).
const flow = vi.hoisted(() => ({ seen: undefined as unknown }))
vi.mock('../report/ReportFlowProvider', () => ({
  useOwnPin: () => undefined,
  useSeenOnMap: () => flow.seen,
}))

const API = 'https://api.example.test'
const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
// Task 6's seeded pins: A is live at 10 min with no flags, B live at 25 min with 2 flags, 90 m from A; C is live at
// 90 min; D is live at 200 min (past 3 hours); E is a demo photo from 2009.
const A = 'r_1a2b3c4d5e6f40718293a4b5c6d7e8f9'
const B = 'r_2b3c4d5e6f7a41829304b5c6d7e8f9a0'
const C = 'r_3c4d5e6f7a8b429304a5b6c7d8e9f0a1'
const D = 'r_4d5e6f7a8b9c43a405b6c7d8e9f0a1b2'
const E = 'r_5e6f7a8b9c0d44b506c7d8e9f0a1b2c3'
const text = (key: StringKey) => EN[key].text
const ID_PATTERN = /r_[0-9a-f]{32}/

polyfillDialog()

// ---- helpers ----

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response> | undefined
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

function api(scenario: Scenario = 'level_knee', ...handlers: Handler[]) {
  const base = createMockFetch({ scenario, now: () => Date.now() })
  const calls: { url: string; method: string }[] = []
  net.fetch = async (input, init) => {
    const url = String(input)
    calls.push({ url, method: (init?.method ?? 'GET').toUpperCase() })
    for (const handler of handlers) {
      const answer = handler(url, init)
      if (answer !== undefined) return answer
    }
    return base(input, init)
  }
  return calls
}

// The map's answer, with this pin's flag count set.
const mapShowing =
  (id: string, flags: number): Handler =>
  (url) => {
    if (!url.endsWith('/map/pins')) return undefined
    const base = createMockFetch({ now: () => Date.now() })
    return base(url).then(async (res) => {
      const body = (await res.json()) as { pins: Pin[] }
      return json({ pins: body.pins.map((pin) => (pin.id === id ? { ...pin, flags } : pin)) })
    })
  }

const flagAnswers = (...answers: (number | 'network' | 404)[]): Handler => {
  const queue = [...answers]
  return (url) => {
    if (!url.endsWith('/flag')) return undefined
    const next = queue.shift()
    if (next === 'network') throw new TypeError('network')
    if (next === 404) return json({ error: 'not_found' }, 404)
    return json({ flags: next ?? 0 })
  }
}

function renderPin(id: string, { apiUrl = API, lang = 'en' } = {}) {
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  return render(
    <LanguageProvider>
      <main>
        <PinScreen apiUrl={apiUrl} id={id} />
      </main>
    </LanguageProvider>,
  )
}

// Waits for the pin to be read and its card drawn.
const shown = () => screen.findByRole('article')
const flagButton = () => screen.getByRole('button', { name: text('pin.flag') })
const dialog = () => screen.queryByRole('dialog')
const reportCalls = () => vi.mocked(getReport).mock.calls

beforeEach(() => {
  vi.mocked(getPins).mockClear()
  vi.mocked(getReport).mockClear()
  vi.mocked(flagPin).mockClear()
  flow.seen = vi.fn()
  resetPinMemory()
  api()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  sessionStorage.clear()
  document.documentElement.removeAttribute('lang')
})

// ---- what it shows ----

describe('a live pin', () => {
  it("reads GET /map/pins, then calls getReport with the pin's id, and shows the result card with its blurred photo", async () => {
    const calls = api()
    renderPin(B)
    const card = await shown()

    // The API's own two calls, in this order; the card then reads the layers file the report links (not on the API).
    expect(calls.map((call) => call.url).filter((url) => url.startsWith(API))).toEqual([`${API}/map/pins`, `${API}/reports/${B}`])
    expect(getReport).toHaveBeenCalledExactlyOnceWith(API, B)
    expect(card.getAttribute('data-outcome')).toBe('level')
    expect(within(card).getByText('Half-tire deep at this spot (MMDA level).')).toBeTruthy()

    const expected = ((await (await net.fetch(`${API}/reports/${B}`)).json()) as { photoUrl: string }).photoUrl
    const photo = screen.getByRole('img', { name: text('sample.photoAlt') })
    expect(photo.getAttribute('src')).toBe(expected)
    expect(screen.getByText(`${text('sample.edited')} ${text('sample.outlines')}`)).toBeTruthy()
  })

  it("draws the photo once, in the card, under the level line: pin detail has no photo of its own", async () => {
    renderPin(B)
    const card = await shown()
    const photos = screen.getAllByRole('img', { name: text('sample.photoAlt') })
    expect(photos).toHaveLength(1)
    expect(card.contains(photos[0])).toBe(true)
    expect(screen.getAllByText(new RegExp(`^${text('sample.edited')}`))).toHaveLength(1)
    expect(screen.getAllByRole('figure')).toHaveLength(1)
    const level = within(card).getByText('Half-tire deep at this spot (MMDA level).')
    expect(Boolean(level.compareDocumentPosition(photos[0]) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true)
  })

  it("draws the same overlay from the pin's links: the layers file's marks, each reference with its label", async () => {
    renderPin(B)
    const card = await shown()
    const svg = await within(card).findByTestId('overlay-svg')
    expect(svg.getAttribute('viewBox')).toBe('0 0 800 600')
    expect(svg.querySelectorAll('[data-ref]').length).toBeGreaterThan(0)
    expect(svg.querySelector('[data-layer="water"]')).toBeTruthy()
    for (const group of svg.querySelectorAll('[data-ref]')) expect(group.getAttribute('aria-label')).toBeTruthy()
    expect(within(card).getByText(`${text('sample.edited')} ${text('sample.outlines')}`)).toBeTruthy()
    expect(document.body.textContent).not.toMatch(ID_PATTERN)
  })

  it("reads the layers file through the report's own link, and shows the overlay JPEG when that link fails", async () => {
    api('level_knee', (url) => (url.includes('/layers/') ? json({ error: 'AccessDenied' }, 403) : undefined))
    renderPin(B)
    const card = await shown()
    await waitFor(() => expect(card.querySelectorAll('img[src^="data:image"]')).toHaveLength(2))
    expect(within(card).queryByTestId('overlay-svg')).toBeNull()
    expect(within(card).getByRole('img', { name: text('sample.photoAlt') })).toBeTruthy()
  })

  it('shows the age and the number of other live reports within 300 m in the last 3 hours', async () => {
    renderPin(B)
    const card = await shown()
    expect(within(card).getByText('Photo taken 25 min ago. Location within 8 m.')).toBeTruthy()
    expect(screen.getByText('Other reports within 300 m, last 3 hours: 1')).toBeTruthy()
  })

  it('shows the flag count when it is above 0, and not when it is 0', async () => {
    renderPin(B)
    await shown()
    expect(screen.getByText('2 phones have flagged this report as wrong or fake.')).toBeTruthy()

    cleanup()
    renderPin(A)
    await shown()
    expect(screen.queryByText(/flagged this report/)).toBeNull()
  })

  it('says "1 phone" for one flag', async () => {
    api('level_knee', mapShowing(A, 1))
    renderPin(A)
    await shown()
    expect(screen.getByText('1 phone has flagged this report as wrong or fake.')).toBeTruthy()
  })

  it('shows a faded pin, and a floor reading as a floor', async () => {
    renderPin(C)
    const card = await shown()
    expect(within(card).getByText('At least tire deep at this spot (MMDA level).')).toBeTruthy()
  })

  it('has a link back to the map and no Demo badge, and shows no report id as text', async () => {
    renderPin(B)
    await shown()
    expect(screen.getByRole('link', { name: text('map.back') }).getAttribute('href')).toBe('#/map')
    expect(screen.queryByText('Demo')).toBeNull()
    expect(document.body.textContent).not.toMatch(ID_PATTERN)
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(text('pin.title'))
  })

  it('tells the flow about the list it read, so its own pin clears when the map holds it', async () => {
    renderPin(B)
    await shown()
    expect(flow.seen).toHaveBeenCalledTimes(1)
    expect(vi.mocked(flow.seen as ReturnType<typeof vi.fn>).mock.calls[0]?.[0]).toHaveLength(5)
  })

  it('shows a Taglish screen its Taglish lines', async () => {
    renderPin(B, { lang: 'fil' })
    await shown()
    expect(screen.getByRole('link', { name: FIL['map.back'].text })).toBeTruthy()
    expect(screen.getByRole('button', { name: FIL['pin.flag'].text })).toBeTruthy()
    expect(screen.getByText(FIL['pin.nearby'].text.replace('{count}', '1'))).toBeTruthy()
  })
})

describe('a demo pin', () => {
  it("shows the Demo badge, the photo's date, place and event, the credit line and the photo, and has no flag button", async () => {
    renderPin(E)
    const card = await shown()

    expect(getReport).toHaveBeenCalledExactlyOnceWith(API, E)
    expect(within(card).getByText('Demo')).toBeTruthy()
    expect(within(card).getByText('Photo from Sep 26, 2009, Marikina, Typhoon Ondoy')).toBeTruthy()
    expect(
      within(card).getByText('Photo: Example Contributor (mock), CC BY 4.0, faces and plates blurred by Lusot'),
    ).toBeTruthy()
    expect(within(card).getByRole('img', { name: text('sample.photoAlt') }).getAttribute('src')).toMatch(/^data:image/)
    expect(screen.queryByRole('button', { name: text('pin.flag') })).toBeNull()
    expect(screen.queryByText(/Photo taken/)).toBeNull()
  })

  it('shows its nearby count too, and a count of 0 as a number, not as a claim about the spot', async () => {
    renderPin(E)
    await shown()
    expect(screen.getByText('Other reports within 300 m, last 3 hours: 0')).toBeTruthy()
  })
})

// ---- opened directly, and gone ----

describe('opened directly at #/pin/<id>', () => {
  it('reads the map for the pin first, and asks for the report only for an id the map holds', async () => {
    const calls = api()
    renderPin(A)
    await shown()
    const own = calls.filter((call) => call.url.startsWith(API))
    expect(own[0]).toEqual({ url: `${API}/map/pins`, method: 'GET' })
    expect(own).toHaveLength(2)
  })

  it.each([
    ['an id the map does not hold', 'r_00000000000000000000000000000000'],
    ['a pin past 3 hours, though the API still lists it', D],
  ])('shows "This pin is no longer on the map." and no card for %s, and never asks for its report', async (_name, id) => {
    renderPin(id)
    expect(await screen.findByText(text('pin.gone'))).toBeTruthy()

    expect(screen.queryByRole('article')).toBeNull()
    expect(reportCalls()).toHaveLength(0)
    expect(screen.getByRole('link', { name: text('map.back') }).getAttribute('href')).toBe('#/map')
    expect(screen.queryByRole('button', { name: text('pin.flag') })).toBeNull()
  })

  it('shows the same line when the report is not there any more', async () => {
    api('level_knee', (url) => (url === `${API}/reports/${B}` ? json({ error: 'not_found' }, 404) : undefined))
    renderPin(B)
    expect(await screen.findByText(text('pin.gone'))).toBeTruthy()
    expect(screen.queryByRole('article')).toBeNull()
  })

  it('makes no call without an API address, and says so plainly', async () => {
    renderPin(A, { apiUrl: '' })
    expect(await screen.findByText(text('map.noApi'))).toBeTruthy()
    expect(getPins).not.toHaveBeenCalled()
    expect(getReport).not.toHaveBeenCalled()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('says it is loading while the map is read, and keeps the heading', async () => {
    api('level_knee', () => new Promise<Response>(() => {}))
    renderPin(A)
    expect(screen.getByText(text('pin.loading'))).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(text('pin.title'))
  })

  it('says it could not load when the map read fails, and "Try again" reads it again', async () => {
    let fail = true
    api('level_knee', (url) => {
      if (url.endsWith('/map/pins') && fail) throw new TypeError('network')
      return undefined
    })
    renderPin(A)
    expect(await screen.findByText(text('pin.loadFailed'))).toBeTruthy()
    expect(screen.queryByText(text('pin.gone'))).toBeNull()
    expect(reportCalls()).toHaveLength(0)

    fail = false
    fireEvent.click(screen.getByRole('button', { name: text('result.tryAgain') }))
    await shown()
    expect(screen.queryByText(text('pin.loadFailed'))).toBeNull()
  })

  it("shows the pin's own card and says the photo did not load when the report read fails", async () => {
    api('level_knee', (url) => {
      if (url === `${API}/reports/${B}`) throw new TypeError('network')
      return undefined
    })
    renderPin(B)
    const card = await shown()
    expect(within(card).getByText('Half-tire deep at this spot (MMDA level).')).toBeTruthy()
    expect(screen.getByText(text('pin.photoFailed'))).toBeTruthy()
    expect(screen.queryByRole('img')).toBeNull()
  })
})

// ---- the photo's link ----

describe('an expired photo link', () => {
  it('asks the API for a new link once, and a second failure leaves the card without asking again', async () => {
    renderPin(B)
    await shown()
    expect(reportCalls()).toHaveLength(1)

    fireEvent.error(screen.getByRole('img', { name: text('sample.photoAlt') }))
    await waitFor(() => expect(reportCalls()).toHaveLength(2))
    await act(async () => {})
    fireEvent.error(screen.getByRole('img', { name: text('sample.photoAlt') }))
    await act(async () => {})
    expect(reportCalls()).toHaveLength(2)
  })

  it("does the same for a demo pin's photo, which the card draws", async () => {
    renderPin(E)
    const card = await shown()
    fireEvent.error(within(card).getByRole('img', { name: text('sample.photoAlt') }))
    await waitFor(() => expect(reportCalls()).toHaveLength(2))
  })

  it('leaves the card without a photo, and without an error screen, after the second failure', async () => {
    renderPin(B)
    const card = await shown()
    fireEvent.error(screen.getByRole('img', { name: text('sample.photoAlt') }))
    await waitFor(() => expect(reportCalls()).toHaveLength(2))
    await act(async () => {})
    fireEvent.error(screen.getByRole('img', { name: text('sample.photoAlt') }))
    await act(async () => {})

    expect(screen.queryByRole('img', { name: text('sample.photoAlt') })).toBeNull()
    expect(screen.queryByRole('figure')).toBeNull()
    expect(within(card).getByText('Half-tire deep at this spot (MMDA level).')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByText(text('pin.photoFailed'))).toBeNull()
    expect(screen.queryByText(text('pin.gone'))).toBeNull()
  })
})

// ---- focus ----

describe('focus', () => {
  const heading = () => screen.getByRole('heading', { level: 1 })

  it('goes to the heading when the screen opens, and is still there when the card shows', async () => {
    renderPin(B)
    expect(document.activeElement).toBe(heading())
    expect(heading().getAttribute('tabindex')).toBe('-1')
    await shown()
    expect(document.activeElement).toBe(heading())
  })

  it('is on the heading when the pin turns out to be gone', async () => {
    renderPin('r_00000000000000000000000000000000')
    await screen.findByText(text('pin.gone'))
    expect(document.activeElement).toBe(heading())
  })

  it('stays where it is when it is somewhere already', async () => {
    const outside = document.createElement('button')
    document.body.append(outside)
    outside.focus()
    renderPin(B)
    await shown()
    expect(document.activeElement).toBe(outside)
    outside.remove()
  })

  it('comes back to the heading when "Try again" removes the button that was pressed', async () => {
    let fail = true
    api('level_knee', (url) => {
      if (url.endsWith('/map/pins') && fail) throw new TypeError('network')
      return undefined
    })
    renderPin(A)
    await screen.findByText(text('pin.loadFailed'))
    const retry = screen.getByRole('button', { name: text('result.tryAgain') })
    retry.focus()

    fail = false
    fireEvent.click(retry)
    await shown()
    expect(document.activeElement).toBe(heading())
  })

  it("goes to the heading when a flag's 404 turns the screen to gone and takes the button that had focus", async () => {
    api('level_knee', flagAnswers(404))
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    await screen.findByText(text('pin.gone'))
    // The heading takes focus in an effect, which can come a moment after the text it goes with.
    await waitFor(() => expect(document.activeElement).toBe(heading()))
  })
})

// ---- the status lines ----

describe('the status line', () => {
  // The one line is in the page from the first draw, so a change to its text is announced.
  const statusWhileLoading = () => {
    const status = screen.getByText(text('pin.loading'))
    expect(status.getAttribute('role')).toBe('status')
    return status
  }

  it('is one element from loading to gone', async () => {
    renderPin('r_00000000000000000000000000000000')
    const status = statusWhileLoading()
    expect(await screen.findByText(text('pin.gone'))).toBe(status)
  })

  it('is one element from loading to could-not-load', async () => {
    api('level_knee', (url) => {
      if (url.endsWith('/map/pins')) throw new TypeError('network')
      return undefined
    })
    renderPin(A)
    const status = statusWhileLoading()
    expect(await screen.findByText(text('pin.loadFailed'))).toBe(status)
  })

  it('is one element from loading to a card that has no photo, and is empty when the photo loaded', async () => {
    api('level_knee', (url) => {
      if (url === `${API}/reports/${B}`) throw new TypeError('network')
      return undefined
    })
    renderPin(B)
    const status = statusWhileLoading()
    await shown()
    expect(screen.getByText(text('pin.photoFailed'))).toBe(status)

    cleanup()
    api()
    renderPin(B)
    const again = statusWhileLoading()
    await shown()
    expect(again.textContent).toBe('')
    expect(again.isConnected).toBe(true)
  })

  it('has the "Flagged" line in the page, empty, before the flag, and fills that same element', async () => {
    api('level_knee', flagAnswers(3))
    renderPin(B)
    await shown()
    const flagged = document.querySelector('[role="status"][tabindex="-1"]') as HTMLElement
    expect(flagged.textContent).toBe('')

    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    expect(await screen.findByText(text('pin.flagged'))).toBe(flagged)
  })

  it('has the flag-failed line in the page, empty, and fills that same element when the send fails', async () => {
    api('level_knee', flagAnswers('network'))
    renderPin(B)
    await shown()
    const before = [...document.querySelectorAll('[role="status"]')]
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    const line = await screen.findByText(text('pin.flagFailed'))
    expect(before).toContain(line)
    expect([...document.querySelectorAll('[role="status"]')]).toEqual(before)
  })
})

// ---- the flag ----

describe('Flag as wrong or fake', () => {
  it('asks first, in a dialog of its own with the screen line, and not in the browser', async () => {
    const confirm = vi.spyOn(window, 'confirm')
    const alert = vi.spyOn(window, 'alert')
    const prompt = vi.spyOn(window, 'prompt')
    const showModal = vi.spyOn(HTMLDialogElement.prototype, 'showModal')
    renderPin(B)
    await shown()
    expect(dialog()).toBeNull()

    fireEvent.click(flagButton())
    const box = screen.getByRole('dialog')
    expect(showModal).toHaveBeenCalledTimes(1)
    expect(within(box).getByRole('heading', { name: text('flag.title') })).toBeTruthy()
    expect(within(box).getByText(text('flag.body'))).toBeTruthy()
    expect(within(box).getByText(SCREEN_LINE).getAttribute('lang')).toBe('en')
    expect(flagPin).not.toHaveBeenCalled()
    for (const spy of [confirm, alert, prompt]) expect(spy).not.toHaveBeenCalled()
  })

  it('puts focus in the dialog, on the button that leaves things as they were', async () => {
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    expect(document.activeElement).toBe(within(screen.getByRole('dialog')).getByRole('button', { name: text('flag.cancel') }))
  })

  it.each([
    ['Escape', () => fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })],
    ['the cancel button', () => fireEvent.click(screen.getByRole('button', { name: text('flag.cancel') }))],
  ] as const)('closes on %s without flagging, and returns focus to the button', async (_name, close) => {
    renderPin(B)
    await shown()
    const button = flagButton()
    fireEvent.click(button)
    close()

    expect(dialog()).toBeNull()
    expect(flagPin).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(button)
    expect(screen.queryByText(text('pin.flagged'))).toBeNull()
  })

  it('calls flagPin once after the person says yes, with the pin and the device, and shows "Flagged" for the rest of the visit', async () => {
    api('level_knee', flagAnswers(3))
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))

    expect(await screen.findByText(text('pin.flagged'))).toBeTruthy()
    expect(flagPin).toHaveBeenCalledExactlyOnceWith(API, B, getDeviceId())
    expect(dialog()).toBeNull()
    expect(screen.queryByRole('button', { name: text('pin.flag') })).toBeNull()
    expect(screen.getByText(text('pin.flagged')).closest('[role="status"]')).not.toBeNull()

    // Leaving and coming back in the same visit still says so.
    cleanup()
    renderPin(B)
    await shown()
    expect(screen.getByText(text('pin.flagged'))).toBeTruthy()
    expect(screen.queryByRole('button', { name: text('pin.flag') })).toBeNull()
    expect(flagPin).toHaveBeenCalledTimes(1)
  })

  it('calls flagPin once for two presses of "Flag it" in the same moment', async () => {
    api('level_knee', flagAnswers(3))
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    const yes = screen.getByRole('button', { name: text('flag.confirm') })
    act(() => {
      yes.click()
      yes.click()
    })
    await screen.findByText(text('pin.flagged'))
    expect(flagPin).toHaveBeenCalledTimes(1)
  })

  it('moves focus to "Flagged" once the flag button is gone, so it is not lost', async () => {
    api('level_knee', flagAnswers(3))
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    const flagged = await screen.findByText(text('pin.flagged'))
    // Focus moves in an effect, which can come a moment after the text it goes with.
    await waitFor(() => expect(document.activeElement).toBe(flagged.closest('[tabindex]')))
  })

  it('shows "Flagged" for a repeat too, with the count unchanged', async () => {
    api('level_knee', mapShowing(B, 2), flagAnswers(2))
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    expect(await screen.findByText(text('pin.flagged'))).toBeTruthy()
    expect(screen.getByText('2 phones have flagged this report as wrong or fake.')).toBeTruthy()
  })

  it('says it could not send when the call fails, keeps the button, and lets the person try again', async () => {
    api('level_knee', flagAnswers('network', 5))
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))

    expect(await screen.findByText(text('pin.flagFailed'))).toBeTruthy()
    expect(screen.queryByText(text('pin.flagged'))).toBeNull()
    expect(dialog()).toBeNull()

    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    expect(await screen.findByText(text('pin.flagged'))).toBeTruthy()
    expect(screen.queryByText(text('pin.flagFailed'))).toBeNull()
    expect(flagPin).toHaveBeenCalledTimes(2)
  })

  it('says the pin is no longer on the map when the API says it is not there', async () => {
    api('level_knee', flagAnswers(404))
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    expect(await screen.findByText(text('pin.gone'))).toBeTruthy()
    expect(screen.queryByRole('article')).toBeNull()
  })

  it('remembers a flag whose answer comes after the person left: the count and "Flagged" are kept for the visit', async () => {
    const answer = deferred<Response>()
    api('level_knee', mapShowing(B, 3), (url) => (url.endsWith('/flag') ? answer.promise : undefined))
    const { unmount } = renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    await waitFor(() => expect(flagPin).toHaveBeenCalledTimes(1))
    unmount()

    await act(async () => answer.resolve(json({ flags: 7 })))
    expect(wasFlagged(B)).toBe(true)
    expect(flagCount(B, 0)).toBe(7)
  })

  it('has the dialog in Taglish too, with the screen line still in English', async () => {
    renderPin(B, { lang: 'fil' })
    await shown()
    fireEvent.click(screen.getByRole('button', { name: FIL['pin.flag'].text }))
    const box = screen.getByRole('dialog')
    expect(within(box).getByRole('heading', { name: FIL['flag.title'].text })).toBeTruthy()
    expect(within(box).getByText(SCREEN_LINE)).toBeTruthy()
  })
})

describe('a flag count never goes down', () => {
  async function flagIt() {
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    await screen.findByText(text('pin.flagged'))
  }

  it('with the map showing 3 flags, a flag answering { flags: 2 } still shows 3', async () => {
    api('level_knee', mapShowing(B, 3), flagAnswers(2))
    renderPin(B)
    await shown()
    expect(screen.getByText('3 phones have flagged this report as wrong or fake.')).toBeTruthy()
    await flagIt()
    expect(screen.getByText('3 phones have flagged this report as wrong or fake.')).toBeTruthy()
    expect(screen.queryByText(/^2 phones/)).toBeNull()
  })

  it('and a later map read of 1 still shows 3', async () => {
    api('level_knee', mapShowing(B, 3), flagAnswers(2))
    renderPin(B)
    await shown()
    await flagIt()
    cleanup()

    api('level_knee', mapShowing(B, 1))
    renderPin(B)
    await shown()
    expect(screen.getByText('3 phones have flagged this report as wrong or fake.')).toBeTruthy()
  })

  it('and an answer of 4 shows 4', async () => {
    api('level_knee', mapShowing(B, 3), flagAnswers(4))
    renderPin(B)
    await shown()
    await flagIt()
    expect(screen.getByText('4 phones have flagged this report as wrong or fake.')).toBeTruthy()
  })

  it("takes the map screen's read into account too: a count the map showed is not shown lower here", async () => {
    // The map read this pin with 5 flags earlier in the visit (it records every read), then the API said 4.
    flagCount(B, 5)
    api('level_knee', mapShowing(B, 4))
    renderPin(B)
    await shown()
    expect(screen.getByText('5 phones have flagged this report as wrong or fake.')).toBeTruthy()
  })
})

// ---- privacy ----

describe('privacy', () => {
  it('writes nothing to storage and nothing to the console, and shows no position or report id', async () => {
    const consoles = (['log', 'info', 'warn', 'error', 'debug'] as const).map((name) =>
      vi.spyOn(console, name).mockImplementation(() => {}),
    )
    api('level_knee', flagAnswers(3))
    renderPin(B)
    await shown()
    fireEvent.click(flagButton())
    fireEvent.click(screen.getByRole('button', { name: text('flag.confirm') }))
    await screen.findByText(text('pin.flagged'))

    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    for (const spy of consoles) expect(spy).not.toHaveBeenCalled()
    expect(document.body.textContent).not.toMatch(ID_PATTERN)
    expect(document.body.textContent).not.toMatch(/14\.61|120\.98/)
  })
})
