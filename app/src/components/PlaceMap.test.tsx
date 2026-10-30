import { act, cleanup, fireEvent, render } from '@testing-library/react'
import L from 'leaflet'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../i18n'
import { distanceM, type Fix, type LatLng } from '../lib/geo'
import { offsetM } from '../test/geo'
import { PlaceMap } from './PlaceMap'

// The map's own part of the 100 m limit: every position it reports through onPlace is already within 100 m of the fix,
// whether it came from a tap, a drag or a key. PlaceStep holds the limit again (PlaceStep.limit.test.tsx).
const FIX: Fix = { lat: 14.6123456, lng: 121.0456789, accuracyM: 30 }

let map: L.Map
let marker: L.Marker

beforeEach(() => {
  const makeMap = L.map as unknown as (...args: unknown[]) => L.Map
  const makeMarker = L.marker as unknown as (...args: unknown[]) => L.Marker
  vi.spyOn(L, 'map').mockImplementation(((...args: unknown[]) => (map = makeMap(...args))) as never)
  vi.spyOn(L, 'marker').mockImplementation(((...args: unknown[]) => (marker = makeMarker(...args))) as never)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderMap(placed: LatLng = FIX) {
  const onPlace = vi.fn<(next: LatLng) => void>()
  render(
    <LanguageProvider>
      <PlaceMap fix={FIX} placed={placed} onPlace={onPlace} />
    </LanguageProvider>,
  )
  return onPlace
}

const reported = (onPlace: ReturnType<typeof renderMap>, call = 0) => onPlace.mock.calls[call]?.[0] as LatLng

describe('what the map reports', () => {
  it('holds a tap 300 m away to 100 m from the fix, and leaves a tap 40 m away as it is', () => {
    const onPlace = renderMap()
    act(() => void map.fire('click', { latlng: L.latLng(offsetM(FIX, 0, 300)) }))
    expect(Math.abs(distanceM(FIX, reported(onPlace)) - 100)).toBeLessThan(0.5)

    const near = offsetM(FIX, 0, 40)
    act(() => void map.fire('click', { latlng: L.latLng(near) }))
    expect(reported(onPlace, 1)).toEqual(near)
  })

  it('holds a drop 300 m away to 100 m, and the pin itself stops at 100 m while it is still being dragged', () => {
    const onPlace = renderMap()
    act(() => {
      marker.setLatLng(offsetM(FIX, 300, 0))
      marker.fire('drag')
    })
    expect(Math.abs(distanceM(FIX, marker.getLatLng()) - 100)).toBeLessThan(0.5)

    act(() => void marker.fire('dragend'))
    expect(Math.abs(distanceM(FIX, reported(onPlace)) - 100)).toBeLessThan(0.5)
  })

  it('holds a key press at 100 m: from a pin already there, one more press stays 100 m out', () => {
    const edge = offsetM(FIX, 0, 100)
    const onPlace = renderMap(edge)
    fireEvent.keyDown(marker.getElement() as HTMLElement, { key: 'ArrowRight' })
    expect(Math.abs(distanceM(FIX, reported(onPlace)) - 100)).toBeLessThan(0.5)
  })

  it('reports nothing for a key that is not an arrow, or for a click it never got', () => {
    const onPlace = renderMap()
    fireEvent.keyDown(marker.getElement() as HTMLElement, { key: 'Enter' })
    expect(onPlace).not.toHaveBeenCalled()
  })
})
