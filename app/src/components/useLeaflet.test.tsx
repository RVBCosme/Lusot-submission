import { cleanup, render } from '@testing-library/react'
import L from 'leaflet'
import { StrictMode, useEffect, useRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import indexHtml from '../../index.html?raw'
import useLeafletSource from './useLeaflet.ts?raw'
import { useLeaflet } from './useLeaflet'

const CENTRE = { lat: 14.6, lng: 121 }
let latest: L.Map | undefined

function TestMap({ options = {} }: { options?: L.MapOptions }) {
  const ref = useRef<HTMLDivElement>(null)
  const map = useLeaflet(ref, { center: CENTRE, zoom: 17, ...options })
  useEffect(() => {
    latest = map
  })
  return <div ref={ref} />
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  latest = undefined
})

describe('useLeaflet', () => {
  it('makes a map in the element, at the centre and zoom it was given, and returns it once the element exists', () => {
    const { container } = render(<TestMap />)

    expect(latest).toBeDefined()
    expect(latest?.getContainer()).toBe(container.firstElementChild)
    expect(latest?.getCenter().lat).toBeCloseTo(CENTRE.lat, 5)
    expect(latest?.getCenter().lng).toBeCloseTo(CENTRE.lng, 5)
    expect(latest?.getZoom()).toBe(17)
    expect(container.querySelector('.leaflet-container')).not.toBeNull()
  })

  it('passes Leaflet its own options on, and stops at zoom 19, the highest OpenStreetMap serves', () => {
    render(<TestMap options={{ dragging: false, scrollWheelZoom: false }} />)

    expect(latest?.dragging.enabled()).toBe(false)
    expect(latest?.scrollWheelZoom.enabled()).toBe(false)
    expect(latest?.getMaxZoom()).toBe(19)
  })

  it("takes its tiles from OpenStreetMap's own server and from nowhere else", () => {
    const { container } = render(<TestMap />)

    const tiles = [...container.querySelectorAll<HTMLImageElement>('img.leaflet-tile')]
    expect(tiles.length).toBeGreaterThan(0)
    for (const tile of tiles) expect(tile.src).toMatch(/^https:\/\/tile\.openstreetmap\.org\/17\/\d+\/\d+\.png$/)
  })

  it('shows "© OpenStreetMap contributors" as one link to the copyright page, and no other credit', () => {
    const { container } = render(<TestMap />)

    const control = container.querySelector('.leaflet-control-attribution')
    expect(control).not.toBeNull()
    const links = control?.querySelectorAll('a') ?? []
    expect(links).toHaveLength(1)
    expect(links[0]?.getAttribute('href')).toBe('https://www.openstreetmap.org/copyright')
    expect(control?.textContent).toBe('© OpenStreetMap contributors')
    expect(links[0]?.getAttribute('target')).toBe('_blank')
    expect(links[0]?.getAttribute('rel')).toBe('noopener')
  })

  it('has one attribution and one tile layer after a StrictMode mount, unmount and mount', () => {
    const { container } = render(
      <StrictMode>
        <TestMap />
      </StrictMode>,
    )

    expect(container.querySelectorAll('.leaflet-control-attribution')).toHaveLength(1)
    expect(container.querySelectorAll('.leaflet-tile-container')).toHaveLength(1)
    expect(container.querySelectorAll('.leaflet-map-pane')).toHaveLength(1)
  })

  it('removes the map when the component goes away', () => {
    const remove = vi.spyOn(L.Map.prototype, 'remove')
    const { unmount } = render(<TestMap />)
    expect(remove).not.toHaveBeenCalled()

    unmount()
    expect(remove).toHaveBeenCalledOnce()
  })

  it('removes the map of a StrictMode mount that was thrown away, and keeps the last one', () => {
    const remove = vi.spyOn(L.Map.prototype, 'remove')
    const { unmount } = render(
      <StrictMode>
        <TestMap />
      </StrictMode>,
    )
    expect(remove).toHaveBeenCalledOnce()
    unmount()
    expect(remove).toHaveBeenCalledTimes(2)
  })

  it('sends no referrer policy of its own: the tile layer sets none and the page has none', () => {
    const tileLayer = vi.spyOn(L, 'tileLayer')
    render(<TestMap />)

    expect(tileLayer).toHaveBeenCalledOnce()
    expect(tileLayer.mock.calls[0]?.[1]).not.toHaveProperty('referrerPolicy')
    expect(indexHtml).not.toMatch(/referrer/i)
    expect(useLeafletSource.replace(/\/\/.*$/gm, '')).not.toMatch(/referrer/i)
  })

  it("imports Leaflet's own stylesheet, and its source has no console call", () => {
    expect(useLeafletSource).toContain("import 'leaflet/dist/leaflet.css'")
    expect(useLeafletSource).not.toMatch(/\bconsole\b/)
  })
})
