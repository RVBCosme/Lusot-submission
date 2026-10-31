import L from 'leaflet'
import { LocateFixedIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { LEVELS } from '../copy/levels'
import { T, useLanguage, useT } from '../i18n'
import type { StringKey } from '../i18n/en'
import type { Pin } from '../lib/api'
import { locateOnce, locationLine } from '../lib/geo'
import { isOwn, pinStrength } from '../map/pins'
import { pinLabel } from '../map/pinWording'
import { useLeaflet } from './useLeaflet'

// Manila, wide enough for the whole of Metro Manila, until there are pins to fit (or a place to go to).
const START = { lat: 14.5995, lng: 120.9842 }
const START_ZOOM = 11
// Street level, where a person can tell which spot is theirs.
const LOCATE_ZOOM = 16
const FIT = { padding: [48, 48] as L.PointTuple, maxZoom: 15, animate: false }

const BUTTON =
  'inline-flex min-h-tap items-center gap-2 rounded-control border-2 border-outline bg-surface px-3 font-bold ' +
  'active:border-ink active:bg-ink active:text-surface'

// A marker's look comes from index.css (.map-pin). The depth is its fill, one hue that deepens with the level, and the
// edge says the rest without colour: a dashed edge is faded, a diamond is a demo photo, a double ring is the person's own.
function iconFor(pin: Pin): L.DivIcon {
  const depth = LEVELS.indexOf(pin.level) + 1
  // No size or anchor here: index.css gives the marker its 48 px touch target and centres it.
  return L.divIcon({
    className: `map-pin map-pin-depth-${depth}`,
    html: '<span class="map-pin-dot"></span>',
    iconSize: undefined,
  })
}

// The map of pins (C612): Leaflet through useLeaflet, a marker for each pin, and "Locate me". The markers are real
// buttons, reachable by keyboard and named by the level line and age; the list beside the map is the screen-reader route.
//
// A marker is made once for a pin and kept: its label, fade and look are updated in place each minute, so a marker the
// keyboard is on isn't replaced under it. The frame closes the map's stacking (`isolate`), so Leaflet's panes and
// controls (z-index 400 to 1,000) can never rise over the layout's screen-line bar, and the credit stays above it.
export function MapView({ pins, now, onOpen }: { pins: readonly Pin[]; now: Date; onOpen(pin: Pin): void }) {
  const t = useT()
  const { lang } = useLanguage()
  const container = useRef<HTMLDivElement>(null)
  const map = useLeaflet(container, { center: START, zoom: START_ZOOM, zoomControl: false })
  const placed = useRef(new Map<string, { marker: L.Marker; kind: string }>())
  // The latest props, for the handlers that Leaflet and the keyboard keep.
  const latest = useRef({ pins, onOpen })
  useEffect(() => {
    latest.current = { pins, onOpen }
  })

  // Zoom buttons that are 48 px targets and named in the page's language.
  const zoomIn = t('map.zoomIn').text
  const zoomOut = t('map.zoomOut').text
  useEffect(() => {
    if (map === undefined) return
    const control = L.control.zoom({ position: 'topright', zoomInTitle: zoomIn, zoomOutTitle: zoomOut }).addTo(map)
    return () => {
      control.remove()
    }
  }, [map, zoomIn, zoomOut])

  // The markers. One for each pin, made when it first shows and removed when it goes.
  useEffect(() => {
    if (map === undefined) return
    const open = (id: string) => {
      const pin = latest.current.pins.find((candidate) => candidate.id === id)
      if (pin !== undefined) latest.current.onOpen(pin)
    }
    const held = placed.current
    const ids = new Set(pins.map((pin) => pin.id))
    for (const [id, { marker }] of held) {
      if (!ids.has(id)) {
        marker.remove()
        held.delete(id)
      }
    }
    for (const pin of pins) {
      const kind = `${pin.level}|${pin.mode}`
      let entry = held.get(pin.id)
      // A pin whose level or kind changed under the same id needs a new icon: replace its marker.
      if (entry !== undefined && entry.kind !== kind) {
        entry.marker.remove()
        entry = undefined
      }
      if (entry === undefined) {
        const marker = L.marker({ lat: pin.lat, lng: pin.lng }, { icon: iconFor(pin), keyboard: true })
        marker.addTo(map)
        marker.on('click', () => open(pin.id))
        // Enter and Space press a button, and this handler is what makes both work: Leaflet 1.9.4 turns an Enter keypress
        // into an action only for a marker with a popup bound, and a div with role="button" gets no click from the
        // browser. preventDefault matters for Space, which would otherwise scroll the page.
        marker.getElement()?.addEventListener('keydown', (event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return
          event.preventDefault()
          event.stopPropagation()
          open(pin.id)
        })
        entry = { marker, kind }
        held.set(pin.id, entry)
      }
      const { marker } = entry
      const at = marker.getLatLng()
      if (at.lat !== pin.lat || at.lng !== pin.lng) marker.setLatLng({ lat: pin.lat, lng: pin.lng })
      const own = isOwn(pin)
      marker.setZIndexOffset(own ? 1000 : pin.mode === 'demo' ? -100 : 0)
      const icon = marker.getElement()
      icon?.classList.toggle('map-pin-faded', pinStrength(pin, now) === 'faded')
      icon?.classList.toggle('map-pin-demo', pin.mode === 'demo')
      icon?.classList.toggle('map-pin-own', own)
      icon?.setAttribute('aria-label', pinLabel(t, lang, pin, now))
    }
  }, [map, pins, now, t, lang])

  // The markers belong to one map; a new map starts with none.
  useEffect(() => {
    const held = placed.current
    return () => held.clear()
  }, [map])

  // The first pins to arrive set the view: all of them, as close as fits. Later reads leave the view alone, since the
  // person may have moved it. A map that has no size yet (hidden) waits for the next read.
  const fitted = useRef(false)
  useEffect(() => {
    if (map === undefined || fitted.current || pins.length === 0 || map.getSize().x === 0) return
    fitted.current = true
    map.fitBounds(L.latLngBounds(pins.map((pin) => [pin.lat, pin.lng] as L.LatLngTuple)), FIT)
  }, [map, pins])

  // Locate me (C612): one position, to centre the map. It makes no pin, uploads nothing, shows the position as no
  // number and keeps nothing. The answer is used where it arrives and not stored. The request can't be called back, so
  // leaving the screen aborts its signal and an answer that comes after is dropped.
  const [locating, setLocating] = useState(false)
  const [problem, setProblem] = useState<StringKey>()
  const asking = useRef(false)
  const stop = useRef<AbortController | null>(null)
  useEffect(
    () => () => {
      stop.current?.abort()
    },
    [],
  )
  function locate() {
    if (asking.current) return
    asking.current = true
    setProblem(undefined)
    setLocating(true)
    const mine = new AbortController()
    stop.current = mine
    locateOnce({ signal: mine.signal })
      .then(
        (at) => {
          if (mine.signal.aborted) return
          fitted.current = true
          map?.setView(at, Math.max(map.getZoom(), LOCATE_ZOOM))
        },
        (err: unknown) => {
          if (!mine.signal.aborted) setProblem(locationLine(err))
        },
      )
      .finally(() => {
        asking.current = false
        if (!mine.signal.aborted) setLocating(false)
      })
  }

  return (
    <div className="flex min-h-56 flex-1 flex-col">
      <div className="relative isolate min-h-56 flex-1 rounded-control border border-outline">
        <button type="button" onClick={locate} className={`absolute left-2 top-2 z-[1000] ${BUTTON}`}>
          <LocateFixedIcon aria-hidden="true" className="size-6" />
          <T k="map.locate" />
        </button>
        <div ref={container} role="group" aria-label={t('map.mapLabel').text} className="absolute inset-0 rounded-control" />
      </div>
      <p role="status" className="mt-2 text-small empty:mt-0">
        {locating ? <T k="report.locating" /> : problem === undefined ? null : <T k={problem} />}
      </p>
    </div>
  )
}
