import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import L from 'leaflet'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../../i18n'
import { EN, type StringKey } from '../../i18n/en'
import { FIL } from '../../i18n/fil'
import { Layout } from '../../layout/Layout'
import { distanceM, type Fix, type LatLng } from '../../lib/geo'
import { writeItem } from '../../lib/storage'
import { offsetM, offsetOf } from '../../test/geo'
import placeMapSource from '../../components/PlaceMap.tsx?raw'
import { PlaceStep, type Place } from './PlaceStep'
import placeStepSource from './PlaceStep.tsx?raw'

const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
const FIX: Fix = { lat: 14.6123456, lng: 121.0456789, accuracyM: 30 }

const text = (key: StringKey) => EN[key].text

// Every map, marker and circle Leaflet makes, in order, so a test can drive them the way a finger would.
const maps: L.Map[] = []
const markers: L.Marker[] = []
const circles: L.Circle[] = []

function capture<K extends 'map' | 'marker' | 'circle'>(name: K, into: unknown[]) {
  const original = L[name] as unknown as (...args: unknown[]) => unknown
  vi.spyOn(L, name).mockImplementation(((...args: unknown[]) => {
    const made = original(...args)
    into.push(made)
    return made
  }) as never)
}

beforeEach(() => {
  maps.length = markers.length = circles.length = 0
  capture('map', maps)
  capture('marker', markers)
  capture('circle', circles)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('lang')
})

function renderStep(fix: Fix = FIX) {
  const onSend = vi.fn()
  const onRetryFix = vi.fn()
  const view = render(
    <LanguageProvider>
      <PlaceStep fix={fix} onSend={onSend} onRetryFix={onRetryFix} />
    </LanguageProvider>,
  )
  return { onSend, onRetryFix, ...view }
}

// What the nth press of Send handed to onSend.
const sent = (onSend: { mock: { calls: unknown[][] } }, call = 0) =>
  onSend.mock.calls[call]?.[0] as LatLng & { nudgeM: number }
const sendButton = () => screen.getByRole('button', { name: text('place.send') })
const pinElement = () => markers[0]?.getElement() as HTMLElement
const place = (point: LatLng) => act(() => void maps[0]?.fire('click', { latlng: L.latLng(point.lat, point.lng) }))

// What the person sees of the pin: where Leaflet holds it now.
const pinAt = () => {
  const { lat, lng } = (markers[0] as L.Marker).getLatLng()
  return { lat, lng }
}

describe('the place step', () => {
  it('shows a heading, the hint, the legend and the map, with one map, one pin and one accuracy circle', () => {
    renderStep()

    expect(screen.getByRole('heading', { name: text('place.title') })).toBeTruthy()
    expect(screen.getByText(text('place.hint'))).toBeTruthy()
    expect(screen.getByText(text('place.legend'))).toBeTruthy()
    expect(screen.getByRole('group', { name: text('place.map') })).toBeTruthy()
    expect(maps).toHaveLength(1)
    expect(markers).toHaveLength(1)
    expect(circles).toHaveLength(1)
  })

  it("draws the fix's accuracy circle, centred on the fix, as long as the accuracy in metres", () => {
    const { container } = renderStep()

    expect(L.circle).toHaveBeenCalledOnce()
    const [centre, options] = vi.mocked(L.circle).mock.calls[0] as unknown as [L.LatLngLiteral, L.CircleOptions]
    expect(centre).toEqual({ lat: FIX.lat, lng: FIX.lng })
    expect(options.radius).toBe(30)
    expect(container.querySelector('path.place-accuracy')).not.toBeNull()
    expect((circles[0] as L.Circle).getRadius()).toBe(30)
  })

  it('puts the pin on the fix and the map on it, and the circle follows another accuracy, leaving one', () => {
    const { rerender, container } = renderStep()
    expect(pinAt()).toEqual({ lat: FIX.lat, lng: FIX.lng })
    expect(maps[0]?.getCenter().lat).toBeCloseTo(FIX.lat, 5)

    const better: Fix = { ...FIX, accuracyM: 12 }
    rerender(
      <LanguageProvider>
        <PlaceStep fix={better} onSend={vi.fn()} onRetryFix={vi.fn()} />
      </LanguageProvider>,
    )
    expect(circles.at(-1)?.getRadius()).toBe(12)
    expect(container.querySelectorAll('path.place-accuracy')).toHaveLength(1)
  })

  // The same step, given another fix without a new key: the way a retry could hand it one (I-1).
  const withFix = (fix: Fix, onSend: (place: Place) => void) => (
    <LanguageProvider>
      <PlaceStep fix={fix} onSend={onSend} onRetryFix={vi.fn()} />
    </LanguageProvider>
  )

  it('given a new fix 300 m away and no remount, sends a point within 100 m of the new fix, with a true nudgeM', () => {
    const { onSend, rerender } = renderStep()
    place(offsetM(FIX, 0, 50))
    const next: Fix = { ...offsetM(FIX, 300, 0), accuracyM: 20 }
    rerender(withFix(next, onSend))
    fireEvent.click(sendButton())

    const got = sent(onSend)
    expect(distanceM(next, got)).toBeLessThanOrEqual(100)
    expect(got.nudgeM).toBe(Math.min(100, Math.round(distanceM(next, got))))
    // The old pin belonged to the old fix: it starts again on the new one, unmoved.
    expect(got).toEqual({ lat: next.lat, lng: next.lng, nudgeM: 0 })
  })

  it('given a new fix, puts the map, the circle and the pin on it, says nothing of a move, and counts from it', () => {
    const { onSend, rerender, container } = renderStep()
    place(offsetM(FIX, 0, 50))
    expect(screen.getByRole('status').textContent).not.toBe('')

    const next: Fix = { ...offsetM(FIX, 300, 0), accuracyM: 20 }
    rerender(withFix(next, onSend))
    expect(distanceM(maps[0]?.getCenter() as LatLng, next)).toBeLessThan(0.5)
    expect(distanceM(pinAt(), next)).toBeLessThan(0.5)
    expect(circles.at(-1)?.getRadius()).toBe(20)
    expect(distanceM(circles.at(-1)?.getLatLng() as LatLng, next)).toBeLessThan(0.5)
    expect(container.querySelectorAll('path.place-accuracy')).toHaveLength(1)
    expect(container.querySelectorAll('.leaflet-marker-icon')).toHaveLength(1)
    expect(screen.getByRole('status').textContent).toBe('')
    expect(screen.queryByRole('button', { name: text('place.reset') })).toBeNull()

    // A move after that is held to 100 m of the new fix and counted from it.
    place(offsetM(next, 0, 30))
    fireEvent.click(sendButton())
    expect(sent(onSend).nudgeM).toBe(30)
    place(offsetM(next, 0, 300))
    fireEvent.click(sendButton())
    expect(sent(onSend, 1).nudgeM).toBe(100)
    expect(Math.abs(distanceM(next, sent(onSend, 1)) - 100)).toBeLessThan(0.5)
  })

  it('keeps its pin when the same fix comes again with only another accuracy', () => {
    const { onSend, rerender } = renderStep()
    const target = offsetM(FIX, 24, 32)
    place(target)
    rerender(withFix({ ...FIX, accuracyM: 12 }, onSend))
    fireEvent.click(sendButton())

    expect(sent(onSend)).toEqual({ lat: target.lat, lng: target.lng, nudgeM: 40 })
  })

  it('puts the status line right above Send in the page, with the legend out of that block, and fixes nothing over the map', () => {
    const { container } = renderStep()
    const status = screen.getByRole('status')
    const block = status.parentElement as HTMLElement

    expect(block.contains(sendButton())).toBe(true)
    expect(block.contains(screen.getByText(text('place.legend')))).toBe(false)
    // The status comes before Send, so it reads above it, and stays in that block as it fills.
    expect(status.compareDocumentPosition(sendButton()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    place(offsetM(FIX, 0, 40))
    expect(block.contains(status)).toBe(true)
    expect(status.textContent).toBe(EN['place.moved'].text.replace('{metres}', '40'))

    // A bar fixed to the bottom of the scrolling area hid the map's edge, its credit and the pin at 360 x 640 (S5-R14).
    expect(container.querySelector('.sticky, .fixed')).toBeNull()
    expect(placeStepSource.replace(/\/\/.*$|\{\/\*[\s\S]*?\*\/\}/gm, '')).not.toMatch(/\bsticky\b|\bfixed\b/)
  })

  it('sends the fix itself with nudgeM 0 when the pin has not moved', () => {
    const { onSend } = renderStep()
    fireEvent.click(sendButton())

    expect(onSend).toHaveBeenCalledExactlyOnceWith({ lat: FIX.lat, lng: FIX.lng, nudgeM: 0 })
  })

  it('after a tap on the map 300 m away, holds the pin at 100 m and sends nudgeM 100', () => {
    const { onSend } = renderStep()
    place(offsetM(FIX, 0, 300))

    expect(Math.abs(distanceM(FIX, pinAt()) - 100)).toBeLessThan(0.5)
    fireEvent.click(sendButton())
    expect(onSend).toHaveBeenCalledOnce()
    const got = sent(onSend)
    expect(got.nudgeM).toBe(100)
    expect(Math.abs(distanceM(FIX, got) - 100)).toBeLessThan(0.5)
    // The same bearing as the tap: due east.
    expect(Math.abs(offsetOf(FIX, got).northM)).toBeLessThan(0.5)
    expect(offsetOf(FIX, got).eastM).toBeGreaterThan(99)
  })

  it('sends the moved position and its rounded distance for a tap 40 m away', () => {
    const { onSend } = renderStep()
    const target = offsetM(FIX, 24, 32)
    place(target)
    fireEvent.click(sendButton())

    expect(onSend).toHaveBeenCalledExactlyOnceWith({ lat: target.lat, lng: target.lng, nudgeM: 40 })
  })

  it('a drag to 300 m is held at 100 m while it is still going, and the drop sends 100', () => {
    const { onSend } = renderStep()
    const marker = markers[0] as L.Marker

    act(() => {
      marker.setLatLng(offsetM(FIX, 300, 0))
      marker.fire('drag')
    })
    expect(Math.abs(distanceM(FIX, pinAt()) - 100)).toBeLessThan(0.5)

    act(() => void marker.fire('dragend'))
    fireEvent.click(sendButton())
    expect(sent(onSend).nudgeM).toBe(100)
  })

  it('a drag to 40 m is left alone, and the drop sends 40', () => {
    const { onSend } = renderStep()
    const marker = markers[0] as L.Marker
    const target = offsetM(FIX, 0, -40)

    act(() => {
      marker.setLatLng(target)
      marker.fire('drag')
      marker.fire('dragend')
    })
    expect(pinAt()).toEqual(target)
    fireEvent.click(sendButton())
    expect(sent(onSend)).toEqual({ lat: target.lat, lng: target.lng, nudgeM: 40 })
  })

  it('moves 10 m east for each press of the right arrow on the pin, and holds at 100 m', () => {
    const { onSend } = renderStep()
    for (let press = 0; press < 3; press += 1) fireEvent.keyDown(pinElement(), { key: 'ArrowRight' })
    fireEvent.click(sendButton())
    expect(sent(onSend).nudgeM).toBe(30)

    for (let press = 0; press < 12; press += 1) fireEvent.keyDown(pinElement(), { key: 'ArrowRight' })
    fireEvent.click(sendButton())
    expect(sent(onSend, 1).nudgeM).toBe(100)
    expect(Math.abs(distanceM(FIX, pinAt()) - 100)).toBeLessThan(0.5)
  })

  it('the four arrows go north, east, south and west, and the pin keeps its focus as it moves', () => {
    renderStep()
    const pin = pinElement()
    pin.focus()
    fireEvent.keyDown(pin, { key: 'ArrowUp' })
    expect(offsetOf(FIX, pinAt()).northM).toBeCloseTo(10, 0)
    fireEvent.keyDown(pin, { key: 'ArrowDown' })
    fireEvent.keyDown(pin, { key: 'ArrowDown' })
    expect(offsetOf(FIX, pinAt()).northM).toBeCloseTo(-10, 0)
    fireEvent.keyDown(pin, { key: 'ArrowLeft' })
    expect(offsetOf(FIX, pinAt()).eastM).toBeCloseTo(-10, 0)
    expect(document.activeElement).toBe(pin)
  })

  it('keeps an arrow key from also scrolling the page, and ignores any other key', () => {
    renderStep()
    const arrow = fireEvent.keyDown(pinElement(), { key: 'ArrowRight' })
    expect(arrow).toBe(false)
    const other = fireEvent.keyDown(pinElement(), { key: 'a' })
    expect(other).toBe(true)
    expect(pinAt()).not.toEqual({ lat: FIX.lat, lng: FIX.lng })
    expect(Math.abs(offsetOf(FIX, pinAt()).eastM - 10)).toBeLessThan(0.5)
  })

  it('names the pin and the map for a screen reader, in the page\'s language', () => {
    renderStep()
    expect(pinElement().getAttribute('aria-label')).toBe(text('place.pin'))
    expect(pinElement().tabIndex).toBe(0)
  })

  it("says how far the pin moved, in a status line, and that it can't go further at 100 m", () => {
    renderStep()
    expect(screen.getByRole('status').textContent).toBe('')

    place(offsetM(FIX, 0, 40))
    expect(screen.getByRole('status').textContent).toBe(EN['place.moved'].text.replace('{metres}', '40'))

    place(offsetM(FIX, 0, 300))
    expect(screen.getByRole('status').textContent).toBe(text('place.atLimit'))
  })

  it('offers "put the pin back" only after a move, and it returns to nudgeM 0 at the fix', () => {
    const { onSend } = renderStep()
    expect(screen.queryByRole('button', { name: text('place.reset') })).toBeNull()

    place(offsetM(FIX, 50, 0))
    fireEvent.click(screen.getByRole('button', { name: text('place.reset') }))
    expect(pinAt()).toEqual({ lat: FIX.lat, lng: FIX.lng })
    expect(screen.queryByRole('button', { name: text('place.reset') })).toBeNull()

    fireEvent.click(sendButton())
    expect(onSend).toHaveBeenCalledExactlyOnceWith({ lat: FIX.lat, lng: FIX.lng, nudgeM: 0 })
  })

  it('asks for the location again through onRetryFix, and sends nothing', () => {
    const { onSend, onRetryFix } = renderStep()
    fireEvent.click(screen.getByRole('button', { name: text('location.retry') }))

    expect(onRetryFix).toHaveBeenCalledOnce()
    expect(onSend).not.toHaveBeenCalled()
  })

  it('never shows the position as numbers, and keeps it out of the page and the console', () => {
    const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((name) =>
      vi.spyOn(console, name).mockImplementation(() => {}),
    )
    renderStep()
    place(offsetM(FIX, 20, 30))
    fireEvent.keyDown(pinElement(), { key: 'ArrowUp' })

    const shown = document.body.textContent ?? ''
    expect(shown).not.toMatch(/14\.6|121\.0/)
    expect(document.body.innerHTML).not.toMatch(/14\.61\d|121\.04\d/)
    for (const spy of spies) expect(spy).not.toHaveBeenCalled()
    for (const source of [placeStepSource, placeMapSource]) expect(source).not.toMatch(/\bconsole\b/)
  })

  it('keeps no position in storage', () => {
    renderStep()
    place(offsetM(FIX, 20, 30))
    expect(JSON.stringify({ ...localStorage })).not.toMatch(/14\.6|121\.0/)
    expect(sessionStorage.length).toBe(0)
  })

  it('has the OpenStreetMap credit as a link inside the screen, and the one screen line outside it', () => {
    render(
      <LanguageProvider>
        <Layout route={{ name: 'report' }} apiReady>
          <PlaceStep fix={FIX} onSend={vi.fn()} onRetryFix={vi.fn()} />
        </Layout>
      </LanguageProvider>,
    )

    const credit = screen.getByRole('link', { name: '© OpenStreetMap contributors' })
    expect(credit.getAttribute('href')).toBe('https://www.openstreetmap.org/copyright')
    expect(screen.getByRole('main').contains(credit)).toBe(true)
    expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
    const line = screen.getByText(SCREEN_LINE)
    expect(line.getAttribute('lang')).toBe('en')
    expect(screen.getByRole('main').contains(line)).toBe(false)
  })

  it("holds Leaflet's stacking inside the map, so its panes (z-index 400 to 1,000) can't rise over the bar", () => {
    const { container } = renderStep()
    const frame = container.querySelector('.leaflet-container')?.parentElement
    expect(frame?.className).toMatch(/\bisolate\b/)
    expect(frame?.className).toMatch(/\brelative\b/)
  })

  it('is not a dialog, a popover or fullscreen, which would cover the screen line', () => {
    const code = [placeStepSource, placeMapSource].map((source) => source.replace(/\/\/.*$/gm, '')).join('\n')
    expect(code).not.toMatch(/showModal|showPopover|requestFullscreen|<dialog|popover/i)
    renderStep()
    expect(document.querySelector('dialog, [popover]')).toBeNull()
  })

  it('has one map, one pin and one circle in the page after a StrictMode mount', () => {
    const { container } = render(
      <StrictMode>
        <LanguageProvider>
          <PlaceStep fix={FIX} onSend={vi.fn()} onRetryFix={vi.fn()} />
        </LanguageProvider>
      </StrictMode>,
    )
    expect(container.querySelectorAll('.leaflet-marker-icon')).toHaveLength(1)
    expect(container.querySelectorAll('path.place-accuracy')).toHaveLength(1)
    expect(container.querySelectorAll('.leaflet-control-attribution')).toHaveLength(1)
  })

  it('takes the Send, hint and retry lines in Taglish on a Taglish screen', () => {
    writeItem('lusot.lang', 'fil')
    renderStep()

    expect(screen.getByRole('button', { name: FIL['place.send'].text })).toBeTruthy()
    expect(screen.getByText(FIL['place.hint'].text)).toBeTruthy()
    expect(screen.getByRole('button', { name: FIL['location.retry'].text })).toBeTruthy()
    expect(pinElement().getAttribute('aria-label')).toBe(FIL['place.pin'].text)
  })

  it('has no crossing advice, road wording or banned word in any of its lines, in either language', () => {
    const keys = (Object.keys(EN) as StringKey[]).filter((key) => key.startsWith('place.') || key.startsWith('location.'))
    expect(keys.length).toBeGreaterThanOrEqual(15)
    for (const key of keys) {
      for (const line of [EN[key].text, FIL[key].text]) {
        expect(line).not.toMatch(/safe|ligtas/i)
        expect(line).not.toMatch(/you can cross|go ahead|pwedeng dumaan|tumawid ka|lusutan mo|you can pass/i)
        expect(line).not.toMatch(/\broad\b|\broute\b|\bstreet\b|\bdaan\b|\bkalsada\b/i)
      }
    }
  })

  it('marks every new line as not yet reviewed, in both tables', () => {
    const keys = (Object.keys(EN) as StringKey[]).filter((key) => key.startsWith('place.') || key.startsWith('location.'))
    for (const key of keys) {
      expect(EN[key].reviewed).toBe(false)
      expect(FIL[key].reviewed).toBe(false)
    }
  })
})
