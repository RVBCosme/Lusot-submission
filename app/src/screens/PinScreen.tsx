import { useCallback, useEffect, useRef, useState } from 'react'
import { FlagDialog } from '../components/FlagDialog'
import { ResultCard } from '../components/ResultCard'
import { T } from '../i18n'
import { flagPin, getPins, getReport, HttpError, type Pin, type ReportResult } from '../lib/api'
import { getDeviceId } from '../lib/device'
import { useHeadingFocus } from '../lib/focus'
import {
  flagCount,
  markFlagged,
  nearbyCount,
  pinStrength,
  readPinId,
  wasFlagged,
  type PinId,
} from '../map/pins'
import { useSeenOnMap } from '../report/ReportFlowProvider'
import { routeHash } from '../router'

const LINK = 'inline-flex min-h-tap items-center text-action underline underline-offset-4'
const BUTTON =
  'inline-flex min-h-tap items-center rounded-control border-2 border-outline px-4 font-bold ' +
  'active:border-ink active:bg-ink active:text-surface'

// What the screen knows, one step at a time. A pin is only ever asked for by an id that `GET /map/pins` held (S5-R5).
type State =
  | { kind: 'loading' }
  | { kind: 'mapFailed' }
  | { kind: 'gone' }
  | {
      kind: 'ready'
      pin: Pin
      pinId: PinId
      // The nearby count is from the same read, so it describes the map as the screen read it.
      nearby: number
      // undefined when the report could not be read: the card then shows the pin's own fields, without links.
      report: ReportResult | undefined
      // Never lower than the highest count already seen for this pin in the visit (C613, amendment 9).
      flags: number
      now: Date
    }

// Pin detail (C613, C614): the result card for a pin on the map, with its blurred photo, how many other reports lie near
// it, how many phones flagged it, and on a live pin the flag. It never shows the pin's id (C610). The pin's own fields
// come from `GET /map/pins`, read again each time the screen opens, and so for a page opened straight at #/pin/<id>
// too; its photo links come from `GET /reports/{id}`, which is asked for only once the map has held the id. An id it no
// longer holds, or one past 3 hours, reads "no longer on the map", with no card.
export function PinScreen({ apiUrl, id }: { apiUrl: string; id: string }) {
  const seenOnMap = useSeenOnMap()
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const alive = useRef(true)
  // The screen takes the focus of the control that opened it (a marker, a list row, "Back to the map"), and again when
  // its content is swapped under focus: "Try again", or a flag's 404 that turns the screen to "gone" (C612).
  const headingRef = useRef<HTMLHeadingElement>(null)
  useHeadingFocus(headingRef, state.kind)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  useEffect(() => {
    if (apiUrl === '') return
    let live = true
    void (async () => {
      let pins: Pin[]
      try {
        pins = await getPins(apiUrl)
      } catch {
        if (live) setState({ kind: 'mapFailed' })
        return
      }
      if (!live) return
      for (const pin of pins) flagCount(pin.id, pin.flags)
      seenOnMap(pins)
      const now = new Date()
      const pinId = readPinId(pins, id)
      const pin = pins.find((candidate) => candidate.id === pinId)
      if (pinId === undefined || pin === undefined || pinStrength(pin, now) === 'gone') {
        setState({ kind: 'gone' })
        return
      }
      let report: ReportResult | undefined
      let unreadable = false
      try {
        report = await getReport(apiUrl, pinId)
      } catch {
        unreadable = true
      }
      if (!live) return
      // A report that is no longer there, though the map held its pin, is as good as gone.
      if (!unreadable && report === undefined) {
        setState({ kind: 'gone' })
        return
      }
      setState({
        kind: 'ready',
        pin,
        pinId,
        nearby: nearbyCount(pin, pins, now),
        report,
        flags: flagCount(pin.id, pin.flags),
        now,
      })
    })()
    return () => {
      live = false
    }
  }, [apiUrl, id, attempt, seenOnMap])

  // A photo link that fails to load is asked for again once, and a second failure leaves the card as it is.
  const refreshed = useRef(false)
  const photoExpired = useCallback(() => {
    if (refreshed.current || state.kind !== 'ready') return
    refreshed.current = true
    getReport(apiUrl, state.pinId).then(
      (report) => {
        if (!alive.current || report === undefined) return
        setState((now) => (now.kind === 'ready' ? { ...now, report } : now))
      },
      () => {},
    )
  }, [apiUrl, state])

  // ---- the flag ----
  const [asking, setAsking] = useState(false)
  const [flagProblem, setFlagProblem] = useState(false)
  const sending = useRef(false)
  const flagButton = useRef<HTMLButtonElement>(null)
  const flaggedLine = useRef<HTMLParagraphElement>(null)
  // Where focus goes next, once the screen has drawn what it goes to.
  const focusNext = useRef<'button' | 'flagged' | null>(null)
  useEffect(() => {
    const want = focusNext.current
    if (want === null) return
    const target = want === 'button' ? flagButton.current : flaggedLine.current
    if (target === null) return
    focusNext.current = null
    target.focus()
  })

  function cancelFlag() {
    focusNext.current = 'button'
    setAsking(false)
  }

  // The first press takes the guard, so two presses in the same moment make one call.
  function confirmFlag() {
    if (sending.current || state.kind !== 'ready') return
    sending.current = true
    focusNext.current = 'button'
    setAsking(false)
    setFlagProblem(false)
    const { pin } = state
    flagPin(apiUrl, state.pinId, getDeviceId())
      .then(
        (answer) => {
          // The visit's memory is kept even if the person has gone: the flag counted on the server.
          markFlagged(pin.id)
          const flags = flagCount(pin.id, answer.flags)
          if (!alive.current) return
          focusNext.current = 'flagged'
          setState((now) => (now.kind === 'ready' ? { ...now, flags } : now))
        },
        (err: unknown) => {
          if (!alive.current) return
          // The API says it holds no such live pin: it left the map.
          if (err instanceof HttpError && err.status === 404) setState({ kind: 'gone' })
          else setFlagProblem(true)
        },
      )
      .finally(() => {
        sending.current = false
      })
  }

  const ready = state.kind === 'ready' ? state : undefined
  const back = (
    <p>
      <a href={routeHash({ name: 'map' })} className={LINK}>
        <T k="map.back" />
      </a>
    </p>
  )

  // One status line, in the page from the first draw and empty when there is nothing to say, so each change to it is
  // announced: loading, then the pin, or that it is gone or could not load, or that its photo could not load. Empty, it
  // adds no gap, since vertical margins in block flow collapse through an empty box.
  const status =
    apiUrl === '' ? null : state.kind === 'loading' ? (
      <T k="pin.loading" />
    ) : state.kind === 'mapFailed' ? (
      <T k="pin.loadFailed" />
    ) : state.kind === 'gone' ? (
      <T k="pin.gone" />
    ) : state.report === undefined ? (
      <T k="pin.photoFailed" />
    ) : null

  // The pin, once the map has held it and the report has answered.
  function pinBody({ pin, report, nearby, flags, now }: Extract<State, { kind: 'ready' }>) {
    const flaggable = pin.mode === 'live'
    const flagged = wasFlagged(pin.id)
    // The card is given the report as GET /reports/{id} answered, with its photo, overlay and layers links, and draws the
    // photo with its overlay itself, for a live pin and a demo pin alike. The pin's own public fields fill what the report
    // leaves out, and a demo pin's mode is the pin's.
    const card: ReportResult | Pin =
      report === undefined
        ? pin
        : {
            ...report,
            mode: pin.mode,
            capturedAt: report.capturedAt ?? pin.capturedAt,
            gpsAccuracyM: report.gpsAccuracyM ?? pin.gpsAccuracyM ?? undefined,
            credit: pin.credit ?? report.credit,
            place: pin.place ?? report.place,
            event: pin.event ?? report.event,
          }
    return (
      <>
        <ResultCard result={card} source="pin" now={now} onPhotoExpired={photoExpired} />

        <div className="space-y-1">
          <p>
            <T k="pin.nearby" vars={{ count: nearby }} />
          </p>
          {flags > 0 && (
            <p>
              <T k={flags === 1 ? 'pin.flags.one' : 'pin.flags.other'} vars={{ count: flags }} />
            </p>
          )}
        </div>

        {flaggable && (
          <div>
            {!flagged && (
              <button ref={flagButton} type="button" onClick={() => setAsking(true)} className={BUTTON}>
                <T k="pin.flag" />
              </button>
            )}
            {/* Both lines are in the page, empty, before they have anything to say. */}
            <p
              ref={flaggedLine}
              role="status"
              tabIndex={-1}
              className="font-bold outline-none not-empty:min-h-tap not-empty:py-3"
            >
              {flagged ? <T k="pin.flagged" /> : null}
            </p>
            <p role="status" className="not-empty:mt-2">
              {flagged ? null : flagProblem ? <T k="pin.flagFailed" /> : null}
            </p>
          </div>
        )}
        {asking && <FlagDialog onConfirm={confirmFlag} onCancel={cancelFlag} />}
      </>
    )
  }

  return (
    <section className="space-y-4">
      <h1 ref={headingRef} className="text-2xl font-bold outline-none">
        <T k="pin.title" />
      </h1>
      <p role="status">{status}</p>
      {apiUrl === '' && (
        <p>
          <T k="map.noApi" />
        </p>
      )}
      {state.kind === 'mapFailed' && (
        <button
          type="button"
          onClick={() => {
            setState({ kind: 'loading' })
            setAttempt((n) => n + 1)
          }}
          className={BUTTON}
        >
          <T k="result.tryAgain" />
        </button>
      )}
      {back}
      {ready !== undefined && pinBody(ready)}
    </section>
  )
}
