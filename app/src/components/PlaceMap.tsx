import L from 'leaflet'
import { useEffect, useRef, useState } from 'react'
import { useT } from '../i18n'
import { clampToRadius, moveM, type Fix, type LatLng } from '../lib/geo'
import { useLeaflet } from './useLeaflet'

// About 87 px for the pin's whole 100 m of travel, on a phone: the pin can reach its limit without leaving the view.
const ZOOM = 17
// One press of an arrow key on the pin.
const KEY_STEP_M = 10
const ARROWS: Record<string, { north: number; east: number }> = {
  ArrowUp: { north: 1, east: 0 },
  ArrowDown: { north: -1, east: 0 },
  ArrowRight: { north: 0, east: 1 },
  ArrowLeft: { north: 0, east: -1 },
}

// The map the fix and the pin sit on. The map holds still on the fix, because the pin can't leave its 100 m: only
// the pin moves, by a drag, a tap on the map, or the arrow keys on the pin (a tap and the keys are the ways to move it
// without dragging). Every position it reports through `onPlace` is already within 100 m of the fix, and a drag is held
// at that edge while it is still going, so the person sees the limit.
//
// The map's stacking is closed inside its frame (`isolate`), so Leaflet's panes and controls (z-index 400 to 1,000)
// can never rise over the layout's screen-line bar. The credit sits on top of the map, inside the frame.
export function PlaceMap({
  fix,
  placed,
  onPlace,
}: {
  fix: Fix
  placed: LatLng
  onPlace(next: LatLng): void
}) {
  const t = useT()
  const container = useRef<HTMLDivElement>(null)
  const map = useLeaflet(container, {
    center: { lat: fix.lat, lng: fix.lng },
    zoom: ZOOM,
    zoomControl: false,
    dragging: false,
    scrollWheelZoom: false,
    doubleClickZoom: false,
    boxZoom: false,
    keyboard: false,
    touchZoom: 'center',
  })
  const [marker, setMarker] = useState<L.Marker>()

  // The latest props, for the handlers that Leaflet keeps.
  const latest = useRef({ fix, placed, onPlace })
  useEffect(() => {
    latest.current = { fix, placed, onPlace }
  })

  // The circle: the fix's accuracy, in metres. Its look is in index.css (.place-accuracy).
  useEffect(() => {
    if (map === undefined) return
    const circle = L.circle(
      { lat: fix.lat, lng: fix.lng },
      { radius: fix.accuracyM, className: 'place-accuracy', interactive: false },
    ).addTo(map)
    return () => {
      circle.remove()
    }
  }, [map, fix.lat, fix.lng, fix.accuracyM])

  // The pin, which starts where the person was placed.
  useEffect(() => {
    if (map === undefined) return
    const start = latest.current.placed
    // No size or anchor here: index.css gives the pin its 48 px touch target from the tokens and centres it.
    const made = L.marker(start, {
      draggable: true,
      keyboard: true,
      icon: L.divIcon({ className: 'place-pin', html: '<span class="place-pin-dot"></span>', iconSize: undefined }),
    }).addTo(map)

    // Within 100 m of the fix, wherever the pin is now.
    const held = () => {
      const at = made.getLatLng()
      const target = { lat: at.lat, lng: at.lng }
      return { target, next: clampToRadius(latest.current.fix, target) }
    }
    made.on('drag', () => {
      const { target, next } = held()
      if (next !== target) made.setLatLng(next)
    })
    made.on('dragend', () => latest.current.onPlace(held().next))

    // The arrow keys move the pin from where it is, and don't also scroll the page.
    const icon = made.getElement()
    const onKey = (event: KeyboardEvent) => {
      const arrow = ARROWS[event.key]
      if (arrow === undefined) return
      event.preventDefault()
      event.stopPropagation()
      const { fix: origin, placed: now, onPlace: place } = latest.current
      place(clampToRadius(origin, moveM(now, arrow.north * KEY_STEP_M, arrow.east * KEY_STEP_M)))
    }
    icon?.addEventListener('keydown', onKey)

    setMarker(made)
    return () => {
      icon?.removeEventListener('keydown', onKey)
      made.remove()
      setMarker(undefined)
    }
    // The pin is made again only for a new map or a new fix; where it is comes from `placed`, below.
  }, [map, fix.lat, fix.lng])

  // A tap on the map puts the pin there, held within 100 m.
  useEffect(() => {
    if (map === undefined) return
    const onTap = (event: L.LeafletMouseEvent) => {
      latest.current.onPlace(clampToRadius(latest.current.fix, { lat: event.latlng.lat, lng: event.latlng.lng }))
    }
    map.on('click', onTap)
    return () => {
      map.off('click', onTap)
    }
  }, [map])

  // The pin follows `placed` (a tap, a key, "put the pin back").
  useEffect(() => {
    if (marker === undefined) return
    const at = marker.getLatLng()
    if (at.lat !== placed.lat || at.lng !== placed.lng) marker.setLatLng({ lat: placed.lat, lng: placed.lng })
  }, [marker, placed.lat, placed.lng])

  // The pin's name for a screen reader, in the page's language.
  const pinName = t('place.pin').text
  useEffect(() => {
    marker?.getElement()?.setAttribute('aria-label', pinName)
  }, [marker, pinName])

  return (
    <div className="relative isolate min-h-56 flex-1 rounded-control border border-outline">
      <div ref={container} role="group" aria-label={t('place.map').text} className="absolute inset-0 rounded-control" />
    </div>
  )
}
