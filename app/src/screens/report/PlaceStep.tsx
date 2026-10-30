import { useId, useState } from 'react'
import { PlaceMap } from '../../components/PlaceMap'
import { T } from '../../i18n'
import { clampToRadius, MAX_NUDGE_M, nudgeM, type Fix, type LatLng } from '../../lib/geo'

// What the step hands on: the position the person settled on, and how far they moved it from the fix (0 to 100).
export type Place = LatLng & { nudgeM: number }

// Pressing a control fills it with ink and turns its text to the page's colour (S5-R6), as on the camera's view.
const PRESSED = 'enabled:active:border-ink enabled:active:bg-ink enabled:active:text-surface'
const BUTTON = `min-h-tap min-w-tap rounded-control border px-4 font-bold ${PRESSED}`
const LINK = 'inline-flex min-h-tap items-center text-action underline underline-offset-4'

// The report flow's place step (C603): the pin on a small map, with the circle of how closely the phone placed the
// person. The pin starts on the fix and may move up to 100 m from it, by a drag, a tap on the map or the arrow keys.
// "Send" gives the flow the position and `nudgeM`, 0 if the pin never moved. A position is private: it is never
// written out as numbers, logged or kept, and what the person sees of a move is its distance.
//
// `fix` is the fix this step was opened with: a new fix needs a new step (the flow keys it). The step sends what it
// is given once per press, so the flow guards against a double tap (Review Focus 1).
export function PlaceStep({
  fix,
  onSend,
  onRetryFix,
}: {
  fix: Fix
  onSend(place: Place): void
  onRetryFix(): void
}) {
  const headingId = useId()
  const [placed, setPlaced] = useState<LatLng>({ lat: fix.lat, lng: fix.lng })
  const moved = nudgeM(fix, placed)

  return (
    <section aria-labelledby={headingId} className="flex min-h-full flex-col">
      <h1 id={headingId} className="text-title font-bold">
        <T k="place.title" />
      </h1>
      <p className="mt-2 max-w-prose text-small text-ink-2">
        <T k="place.hint" />
      </p>
      <div className="mt-3 flex min-h-0 flex-1 flex-col">
        {/* The map holds the pin to 100 m itself; this holds it again, so nothing past 100 m can be sent. */}
        <PlaceMap fix={fix} placed={placed} onPlace={(next) => setPlaced(clampToRadius(fix, next))} />
        <p className="mt-2 text-small text-ink-2">
          <T k="place.legend" />
        </p>
      </div>
      {/* Always in the page, so a screen reader that has it will say what changes in it. */}
      <p role="status" className="mt-1 min-h-6 text-small">
        {moved > 0 &&
          (moved >= MAX_NUDGE_M ? <T k="place.atLimit" /> : <T k="place.moved" vars={{ metres: moved }} />)}
      </p>
      {/* "Send" stays at the bottom of the scrolling area, above the screen line, on a short phone where the step
          is taller than the screen. The map's own stacking is closed (isolate), so this bar is painted over it. */}
      <div className="sticky bottom-0 z-10 bg-surface pt-2">
        <button
          type="button"
          onClick={() => onSend({ lat: placed.lat, lng: placed.lng, nudgeM: moved })}
          className={`${BUTTON} w-full border-action bg-action text-on-action`}
        >
          <T k="place.send" />
        </button>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1">
        {moved > 0 && (
          <button
            type="button"
            onClick={() => setPlaced({ lat: fix.lat, lng: fix.lng })}
            className={`${LINK} cursor-pointer`}
          >
            <T k="place.reset" />
          </button>
        )}
        <button type="button" onClick={onRetryFix} className={`${LINK} cursor-pointer`}>
          <T k="location.retry" />
        </button>
      </div>
    </section>
  )
}
