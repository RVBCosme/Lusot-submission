import { useEffect, useMemo, useRef, useState } from 'react'
import { EmptyMap } from '../components/EmptyMap'
import { MapView } from '../components/MapView'
import { PinList } from '../components/PinList'
import { ResultCard } from '../components/ResultCard'
import { T, useT } from '../i18n'
import { getPins, type Pin } from '../lib/api'
import { useHeadingFocus } from '../lib/focus'
import { useDesktop } from '../lib/useDesktop'
import { flagCount, isOwn, mergeOwnPin, pinStrength } from '../map/pins'
import { useOwnPin, useSeenOnMap } from '../report/ReportFlowProvider'
import { navigate, routeHash } from '../router'

// The map reads again every minute while the page is visible (C612).
const REFRESH_MS = 60_000

// The same pressed look as the language switch: a selected view is filled, a press fills with ink (S5-R6).
const VIEW =
  'min-h-tap min-w-tap rounded-control border border-outline px-3 aria-pressed:border-action aria-pressed:bg-action ' +
  'aria-pressed:text-on-action aria-pressed:underline aria-pressed:decoration-2 active:border-ink active:bg-ink ' +
  'active:text-surface aria-pressed:active:border-ink aria-pressed:active:bg-ink aria-pressed:active:text-surface'
const ACTION =
  'inline-flex min-h-tap items-center rounded-control bg-action px-4 font-bold text-on-action ' +
  'active:bg-ink active:text-surface'

type View = 'map' | 'list'

// The live map (C612) with its list, and the person's own just-sent pin. The screen owns the one refresh timer: it reads
// `GET /map/pins` when it opens, every 60,000 ms while the page is visible, and at once when the page comes back; it
// stops when the page is hidden and when the screen goes. Every list it gets goes to the flow (so the own pin clears
// once the map holds it) and to the flag counts' memory. Without an API address it reads nothing and says so.
//
// From lg (64 rem) the map runs to the edges of the window (Layout.tsx gives the map's screen no side padding), and the
// list opens in a 24 rem panel on its right with the map beside it, where below lg it takes the map's place.
export function MapScreen({ apiUrl }: { apiUrl: string }) {
  const t = useT()
  const desktop = useDesktop()
  const own = useOwnPin()
  const seenOnMap = useSeenOnMap()
  const [view, setView] = useState<View>('map')
  // The own pin whose result is open, by its id, so a later pin of the person's own doesn't open by itself.
  const [ownOpen, setOwnOpen] = useState<string>()
  // undefined until a read has been answered. A failed read keeps the pins already there.
  const [read, setRead] = useState<Pin[]>()
  const [failed, setFailed] = useState(false)
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    if (apiUrl === '') return
    let live = true
    // Only the latest read counts: an older one answering late would put older pins over newer ones.
    let latest = 0
    let timer: ReturnType<typeof setInterval> | undefined
    const readNow = () => {
      const mine = ++latest
      getPins(apiUrl).then(
        (pins) => {
          if (!live || mine !== latest) return
          for (const pin of pins) flagCount(pin.id, pin.flags)
          seenOnMap(pins)
          setRead(pins)
          setFailed(false)
          setNow(new Date())
        },
        () => {
          if (!live || mine !== latest) return
          setFailed(true)
          setNow(new Date())
        },
      )
    }
    const stop = () => {
      clearInterval(timer)
      timer = undefined
    }
    const start = () => {
      stop()
      // The page may have been hidden for a long while: the pins' ages and fades are read from the clock at once, not
      // when the read answers, which on a weak signal can be 15 s.
      setNow(new Date())
      readNow()
      timer = setInterval(readNow, REFRESH_MS)
    }
    const onVisibility = () => (document.visibilityState === 'hidden' ? stop() : start())
    if (document.visibilityState !== 'hidden') start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      live = false
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [apiUrl, seenOnMap])

  // What the map and the list show: the pins read, with the person's own, and none past 3 hours. The list sorts them.
  const shown = useMemo(
    () => mergeOwnPin(read ?? [], own).filter((pin) => pinStrength(pin, now) !== 'gone'),
    [read, own, now],
  )
  const showsEmpty = apiUrl !== '' && read !== undefined && shown.length === 0
  // The own result is the person's, from the pin's own fields. If the pin clears while it is open, back to the map.
  const panel = own !== undefined && ownOpen === own.id ? 'own' : view

  const ownHeading = useRef<HTMLHeadingElement>(null)
  const mapButton = useRef<HTMLButtonElement>(null)
  const returning = useRef(false)
  useEffect(() => {
    if (panel === 'own') ownHeading.current?.focus()
    else if (returning.current) {
      returning.current = false
      mapButton.current?.focus()
    }
  }, [panel])
  // After that, if focus has still fallen to the page (the screen just opened, or the own result went with the focused
  // heading when the own pin cleared), it goes to the screen's heading.
  const heading = useRef<HTMLHeadingElement>(null)
  useHeadingFocus(heading, panel)

  function openOwn() {
    if (own !== undefined) setOwnOpen(own.id)
  }

  // A pin the API holds opens its own screen. The person's own, which it may not hold yet, opens their result here.
  function open(pin: Pin) {
    if (isOwn(pin)) openOwn()
    else navigate({ name: 'pin', id: pin.id })
  }

  return (
    <section className="flex min-h-full flex-col gap-3 lg:gap-0">
      <h1 ref={heading} className="sr-only">
        <T k="nav.map" />
      </h1>

      {panel !== 'own' && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 lg:px-4 lg:py-2">
            <div role="group" aria-label={t('map.viewGroup').text} className="flex gap-1">
              <button
                ref={mapButton}
                type="button"
                aria-pressed={view === 'map'}
                onClick={() => setView('map')}
                className={VIEW}
              >
                <T k="nav.map" />
              </button>
              <button type="button" aria-pressed={view === 'list'} onClick={() => setView('list')} className={VIEW}>
                <T k="map.list" />
              </button>
            </div>
            {apiUrl !== '' && (
              <a href={routeHash({ name: 'report' })} className={ACTION}>
                <T k="map.report" />
              </a>
            )}
          </div>
          {apiUrl === '' && (
            <p className="lg:px-4 lg:pb-2">
              <T k="map.noApi" />
            </p>
          )}
          {/* In the page from the first draw and empty when there is nothing to say, so a change to it is announced.
              Empty, it takes back the gap above it. */}
          <p role="status" className="empty:-mt-3 lg:px-4 lg:empty:mt-0 lg:not-empty:pb-2">
            {apiUrl === '' ? null : failed ? (
              <T k="map.loadFailed" />
            ) : read === undefined ? (
              <T k="map.loading" />
            ) : null}
          </p>
        </>
      )}

      {/* The map stays mounted while the list or the own result shows, so it keeps its view and its tiles. `hidden`
          beats `flex` through Tailwind's base rule [hidden] { display: none !important }, and no class can lift it, so
          from lg the screen asks the window and leaves the map shown beside the list. The row around the map and the list
          gives its children to the section below lg; from lg it is the row of the map and its panel. The panel's inner box
          is out of the row's flow, so a long list scrolls in the panel and never makes the screen taller. */}
      <div className="contents lg:flex lg:min-h-0 lg:flex-1">
        <div
          hidden={panel === 'own' || (panel === 'list' && !desktop)}
          className="flex min-h-0 flex-1 flex-col gap-3 lg:min-w-0 lg:gap-0"
        >
          <MapView pins={shown} now={now} onOpen={open} />
          {showsEmpty && panel === 'map' && <EmptyMap />}
        </div>

        {panel === 'list' && (
          <div className="lg:relative lg:w-96 lg:shrink-0 lg:border-l lg:border-outline">
            <div className="lg:absolute lg:inset-0 lg:overflow-y-auto">
              {showsEmpty ? <EmptyMap /> : <PinList pins={shown} now={now} onOpenOwn={openOwn} />}
            </div>
          </div>
        )}
      </div>

      {panel === 'own' && own !== undefined && (
        <div className="space-y-4 lg:mx-auto lg:w-full lg:max-w-page lg:p-4">
          <h2 ref={ownHeading} tabIndex={-1} className="text-title font-bold outline-none">
            <T k="map.own" />
          </h2>
          <ResultCard result={own} source="own" now={now} />
          <button
            type="button"
            onClick={() => {
              returning.current = true
              setOwnOpen(undefined)
            }}
            className={ACTION}
          >
            <T k="map.back" />
          </button>
        </div>
      )}
    </section>
  )
}
