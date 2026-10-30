import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../../i18n'
import { EN } from '../../i18n/en'
import { distanceM, type Fix, type LatLng } from '../../lib/geo'
import { offsetM, offsetOf } from '../../test/geo'
import { PlaceStep } from './PlaceStep'

// The step holds the pin to 100 m itself, whatever its map says, so no position past 100 m can be sent (C603). The
// map here is a fake that reports the raw positions a broken or bypassed map could, so the step's own limit is what
// these tests see; the real map's limit is tested in PlaceStep.test.tsx.
const fakeMap = vi.hoisted(() => ({ place: (_next: { lat: number; lng: number }) => {} }))
vi.mock('../../components/PlaceMap', () => ({
  PlaceMap: (props: { onPlace(next: { lat: number; lng: number }): void }) => {
    fakeMap.place = props.onPlace
    return null
  },
}))

const FIX: Fix = { lat: 14.6123456, lng: 121.0456789, accuracyM: 30 }

afterEach(cleanup)

function renderStep() {
  const onSend = vi.fn<(place: LatLng & { nudgeM: number }) => void>()
  render(
    <LanguageProvider>
      <PlaceStep fix={FIX} onSend={onSend} onRetryFix={vi.fn()} />
    </LanguageProvider>,
  )
  return onSend
}

const send = () => fireEvent.click(screen.getByRole('button', { name: EN['place.send'].text }))

describe("the step's own limit", () => {
  it('sends a position 100 m from the fix, on the same bearing, with nudgeM 100, when the map reports one 300 m away', () => {
    const onSend = renderStep()
    act(() => fakeMap.place(offsetM(FIX, 300, 0)))
    send()

    const sent = onSend.mock.calls[0]?.[0] as LatLng & { nudgeM: number }
    expect(sent.nudgeM).toBe(100)
    expect(Math.abs(distanceM(FIX, sent) - 100)).toBeLessThan(0.5)
    expect(Math.abs(offsetOf(FIX, sent).eastM)).toBeLessThan(0.5)
    expect(offsetOf(FIX, sent).northM).toBeGreaterThan(99)
    expect(screen.getByRole('status').textContent).toBe(EN['place.atLimit'].text)
  })

  it('sends a position the map reports 5 km away at 100 m too, and one 40 m away as it is', () => {
    const onSend = renderStep()
    act(() => fakeMap.place(offsetM(FIX, 3_000, 4_000)))
    send()
    const far = onSend.mock.calls[0]?.[0] as LatLng & { nudgeM: number }
    expect(far.nudgeM).toBe(100)
    expect(Math.abs(distanceM(FIX, far) - 100)).toBeLessThan(0.5)

    const near = offsetM(FIX, -24, -32)
    act(() => fakeMap.place(near))
    send()
    expect(onSend.mock.calls[1]?.[0]).toEqual({ lat: near.lat, lng: near.lng, nudgeM: 40 })
  })

  it('"Put the pin back" returns to the fix, whatever the map reported before', () => {
    const onSend = renderStep()
    act(() => fakeMap.place(offsetM(FIX, 300, 0)))
    fireEvent.click(screen.getByRole('button', { name: EN['place.reset'].text }))
    send()

    expect(onSend).toHaveBeenCalledExactlyOnceWith({ lat: FIX.lat, lng: FIX.lng, nudgeM: 0 })
  })
})
