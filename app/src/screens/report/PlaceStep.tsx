import { useId, useState, type ReactNode } from 'react'
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
// The 100 m holds against the fix in hand, at the point of use: the position shown, counted and sent is always the
// pin read against the current `fix`, clamped to 100 m of it. A pin belongs to the fix it was put against, so a step
// given another fix without a new key starts on that fix, unmoved, and the map follows. The step sends what it is
// given once per press, so the flow guards against a double tap (Review Focus 1).
export function PlaceStep({
  fix,
  notice,
  onSend,
  onRetryFix,
}: {
  fix: Fix
  // A note the flow shows right under the heading, such as Task 12's small-still warning.
  notice?: ReactNode
  onSend(place: Place): void
  onRetryFix(): void
}) {
  const headingId = useId()
  // Where the pin was last put (as the map reported it) and the fix it was put against.
  const [pin, setPin] = useState<{ from: LatLng; to: LatLng }>()
  const here: LatLng = { lat: fix.lat, lng: fix.lng }
  const placed =
    pin !== undefined && pin.from.lat === here.lat && pin.from.lng === here.lng ? clampToRadius(here, pin.to) : here
  const moved = nudgeM(here, placed)

  return (
    <section aria-labelledby={headingId} className="flex min-h-full flex-col">
      <h1 id={headingId} className="text-title font-bold">
        <T k="place.title" />
      </h1>
      {notice}
      <p className="mt-2 max-w-prose text-small text-ink-2">
        <T k="place.hint" />
      </p>
      <div className="mt-3 flex min-h-0 flex-1 flex-col">
        <PlaceMap fix={fix} placed={placed} onPlace={(next) => setPin({ from: here, to: next })} />
        <p className="mt-2 text-small text-ink-2">
          <T k="place.legend" />
        </p>
      </div>
      {/* The status of the pin's move sits right above "Send", in the flow of the page. Nothing is fixed to the bottom of
          the scrolling area: a bar that stayed there, with or without the status in it, hid the map's lower edge, its
          credit and the pin on a 640 px screen (measured at 360 x 640, in both languages, S5-R14), so on a short phone
          the step scrolls instead and nothing is ever covered. */}
      <div className="mt-2">
        {/* Always in the page, so a screen reader that has it will say what changes in it; no height while empty. */}
        <p role="status" className="pb-2 text-small empty:p-0">
          {moved > 0 &&
            (moved >= MAX_NUDGE_M ? <T k="place.atLimit" /> : <T k="place.moved" vars={{ metres: moved }} />)}
        </p>
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
          <button type="button" onClick={() => setPin(undefined)} className={`${LINK} cursor-pointer`}>
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
