// A thin wrapper over Leaflet 1.9.4, used directly with no react-leaflet (C612): it makes the map in an element the
// caller renders, puts OpenStreetMap's tiles in it with the credit its tile policy asks for, and removes the map when
// the component goes. The place step uses it now and the live map will (Task 13).
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState, type RefObject } from 'react'

const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
// OpenStreetMap's tile policy (and the ODbL) asks for this credit, linked to its copyright page, visible on the map.
// The page never sends a no-referrer policy and the tile layer sets no referrer policy of its own, so the browser's
// default sends the site's origin with each tile request, as the policy requires. The link itself leaves a referrer
// out only if rel says so, which it doesn't.
const ATTRIBUTION = '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a>'

// Makes the map in `el` once the element exists, and returns it from then until the component goes. `opts` are
// Leaflet's own map options, read once, when the map is made: a later change to them does nothing. The tile layer, its
// 19-zoom limit and the attribution are always there, whatever `opts` say, and the control shows only that credit,
// not Leaflet's own "Leaflet" prefix (Leaflet is credited in the README and on the licences page).
export function useLeaflet(el: RefObject<HTMLElement | null>, opts: L.MapOptions): L.Map | undefined {
  const [map, setMap] = useState<L.Map>()
  const options = useRef(opts)

  useEffect(() => {
    const element = el.current
    if (element === null) return
    const made = L.map(element, { ...options.current, attributionControl: true })
    made.attributionControl.setPrefix(false)
    L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(made)
    // A box whose size changes after the map is made (a line appearing beside it, a turned phone) needs Leaflet told.
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(() => made.invalidateSize()) : undefined
    observer?.observe(element)
    setMap(made)
    return () => {
      observer?.disconnect()
      made.remove()
      setMap(undefined)
    }
  }, [el])

  return map
}
