// The report flow, from photo to result (MS5 Task 12), held above the routes so that a wait survives a trip to the
// map. It runs what flow.ts's reducer can't: the location watch, the upload, the poll and the own pin's clock.
// The provider and its hooks stay together as one import, so Fast Refresh reloads the page when this file changes.
/* oxlint-disable react/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { getReport, postToS3, requestUpload, RequestTimeoutError, type Pin } from '../lib/api'
import { NOTICE_VERSION } from '../lib/consent'
import { getDeviceId } from '../lib/device'
import { locationLine, waitForFix, type Fix } from '../lib/geo'
import { pollReport } from '../lib/poll'
import { retryOnce } from '../lib/retry'
import { useRoute } from '../router'
import type { Photo } from '../screens/report/CameraStep'
import type { Place } from '../screens/report/PlaceStep'
import {
  flowReducer,
  holdsPhotoOrReport,
  initialFlow,
  linkReusable,
  OWN_PIN_LIFE_MS,
  ownPinOf,
  PHOTO_LIFE_MS,
  photoUsable,
  survivesLeaving,
  uploadProblem,
  type FlowState,
  type OwnPin,
  type Problem,
  type UploadLink,
} from './flow'

// Whether the report flow holds a photo or a report id now, for the service worker's registration, which runs outside
// React (src/main.tsx). There is one flow per app.
let flowBusy = false
export function reportFlowBusy(): boolean {
  return flowBusy
}

export type ReportFlow = {
  state: FlowState
  // A new photo: the camera, with nothing kept.
  start(): void
  // The camera's first frame (Task 9's onStreamOpen): the location watch starts now, never before (C603).
  streamOpened(): void
  photoTaken(photo: Photo): void
  // "Try the location again": a new watch, the same photo.
  retryFix(): void
  // "Send", once per photo: a second press before the step changes does nothing. It doesn't check the consent notice
  // itself, so every caller goes through useGate('notice') (C605), as ReportScreen does.
  send(place: Place): void
  // "Try again" after an upload problem or a pause: the same photo, and the same link while it is 5 minutes old.
  // Through useGate('notice') too.
  retry(): void
  // "Check again" after "No result yet": the same report, polled again; it never uploads.
  checkAgain(): void
}

type OwnPinState = { pin: OwnPin | undefined; seenOnMap(pins: readonly Pin[]): void }

const FlowContext = createContext<ReportFlow | null>(null)
const OwnPinContext = createContext<OwnPinState | null>(null)

// The browser's own word, read as the upload fails: only an offline browser makes the connection the line's subject.
function seenOffline(problem: Problem): Problem {
  return problem.kind === 'upload' && navigator.onLine === false ? { kind: 'upload', offline: true } : problem
}

// Nothing here logs: an error from the watch, the upload or the poll could carry a position or a report id. Each
// failure is told apart by its type and shown as a line.
export function ReportFlowProvider({ apiUrl, children }: { apiUrl: string; children: ReactNode }) {
  const [state, dispatch] = useReducer(flowReducer, initialFlow)
  // What the service worker's registration reads before it reloads for a new deploy (src/pwa.ts): set before the
  // browser paints the new step, and cleared when the flow goes.
  useLayoutEffect(() => {
    flowBusy = holdsPhotoOrReport(state)
  }, [state])
  useLayoutEffect(
    () => () => {
      flowBusy = false
    },
    [],
  )
  const [ownPin, setOwnPin] = useState<OwnPin>()
  // The state as last rendered, for the handlers, which stay the same from render to render. Written before the
  // browser paints, so a press always reads the step it sees.
  const latest = useRef(state)
  useLayoutEffect(() => {
    latest.current = state
  })
  const route = useRoute()
  const onReport = route.name === 'report'
  const onReportNow = useRef(onReport)
  useLayoutEffect(() => {
    onReportNow.current = onReport
  })
  // Pay once (Review Focus 1): set from the press of "Send" or "Try again" until that upload ends. A ref, not state,
  // so two presses in the same moment, before the step re-renders, still make one upload.
  const busy = useRef(false)
  // Each new photo or closed screen is a new run; an answer for an older run goes nowhere.
  const run = useRef(0)
  const fixGen = useRef(0)
  const fixStop = useRef<AbortController | null>(null)
  const pinTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const stopFix = useCallback(() => {
    fixStop.current?.abort()
    fixStop.current = null
  }, [])

  const watchFix = useCallback(() => {
    stopFix()
    const stop = new AbortController()
    fixStop.current = stop
    const gen = ++fixGen.current
    dispatch({ type: 'fixStarted', gen })
    waitForFix({ signal: stop.signal }).then(
      (fix) => {
        if (!stop.signal.aborted) dispatch({ type: 'fixFound', gen, fix })
      },
      (err: unknown) => {
        if (!stop.signal.aborted) dispatch({ type: 'fixFailed', gen, line: locationLine(err) })
      },
    )
  }, [stopFix])

  const start = useCallback(() => {
    stopFix()
    run.current += 1
    dispatch({ type: 'start' })
  }, [stopFix])

  // Closes the screen's flow: the photo, the position and the report id go, unless an upload or a wait is under way.
  const close = useCallback(() => {
    stopFix()
    run.current += 1
    dispatch({ type: 'leave' })
  }, [stopFix])

  const streamOpened = useCallback(() => {
    if (latest.current.step === 'camera') watchFix()
  }, [watchFix])

  const photoTaken = useCallback((photo: Photo) => dispatch({ type: 'photo', photo }), [])

  // The photo's 15 minutes are up (C635): only a new photo can be sent now.
  const expire = useCallback(() => {
    stopFix()
    dispatch({ type: 'photoExpired' })
  }, [stopFix])

  const retryFix = useCallback(() => {
    const now = latest.current
    if (now.step !== 'place' && now.step !== 'problem') return
    if (now.photo === undefined) return
    if (!photoUsable(now.photo, Date.now())) {
      expire()
      return
    }
    watchFix()
  }, [expire, watchFix])

  // POST /uploads (unless a link under 5 minutes old is in hand), then the photo to S3, each retried at most once
  // by retryOnce (C635), never by a loop of its own. The poll starts from the waiting state (below).
  const upload = useCallback(
    async (photo: Photo, fix: Fix, place: Place, link: UploadLink | undefined) => {
      const mine = run.current
      let target = link
      try {
        if (target === undefined) {
          try {
            const answer = await retryOnce(() =>
              requestUpload(
                apiUrl,
                {
                  lat: place.lat,
                  lng: place.lng,
                  gpsAccuracyM: fix.accuracyM,
                  capturedAt: photo.capturedAt,
                  nudgeM: place.nudgeM,
                  consentVersion: NOTICE_VERSION,
                },
                getDeviceId(),
              ),
            )
            target = { reportId: answer.reportId, upload: answer.upload, at: Date.now() }
          } catch (err) {
            if (mine === run.current) dispatch({ type: 'failed', problem: seenOffline(uploadProblem(err)) })
            return
          }
          if (mine !== run.current) return
          dispatch({ type: 'linked', link: target })
        }
        const { upload: post } = target
        try {
          await retryOnce(() => postToS3(post, photo.blob))
        } catch (err) {
          // Any failure of the photo's own upload can be tried again with the same photo. A timeout or a lost
          // connection may have landed it anyway; an answer from S3 (a 4xx) means S3 kept nothing.
          if (mine !== run.current) return
          const mayHaveLanded = err instanceof TypeError || err instanceof RequestTimeoutError
          dispatch({ type: 'failed', problem: seenOffline({ kind: 'upload' }), mayHaveLanded })
          return
        }
        if (mine === run.current) dispatch({ type: 'uploaded', at: Date.now() })
      } finally {
        busy.current = false
      }
    },
    [apiUrl],
  )

  const send = useCallback(
    (place: Place) => {
      if (busy.current) return
      const now = latest.current
      if (now.step !== 'place' || now.photo === undefined || now.fix.status !== 'found') return
      if (!photoUsable(now.photo, Date.now())) {
        expire()
        return
      }
      busy.current = true
      dispatch({ type: 'send', place })
      void upload(now.photo, now.fix.fix, place, undefined)
    },
    [expire, upload],
  )

  // The old link's 5 minutes are over, but its photo may have reached S3 when that upload timed out or lost its
  // connection. One read of the old report, with no retry (its 15 s limit bounds it), decides: past `pending`, the
  // photo is there, so the flow waits on that report and pays once. `pending`, a 404 or any failure: a new link, as
  // before. A photo still queued reads `pending`, so this narrows the double payment C635 allows; it can't close it.
  const landedOrUpload = useCallback(
    async (photo: Photo, fix: Fix, place: Place, oldId: string) => {
      const mine = run.current
      let landed = false
      try {
        const report = await getReport(apiUrl, oldId)
        landed = report !== undefined && report.status !== 'pending'
      } catch {
        // Unknown, so a new link.
      }
      if (mine !== run.current) {
        busy.current = false
        return
      }
      if (!landed) return upload(photo, fix, place, undefined)
      busy.current = false
      dispatch({ type: 'landed', reportId: oldId, at: Date.now() })
    },
    [apiUrl, upload],
  )

  const retry = useCallback(() => {
    if (busy.current) return
    const now = latest.current
    if (now.step !== 'problem' || now.photo === undefined || now.again === undefined) return
    if (!photoUsable(now.photo, Date.now())) {
      expire()
      return
    }
    const { fix, place, link, mayHaveLanded } = now.again
    // A new link only when the old one is over 5 minutes old; with it, the same report and no second payment.
    const reuse = link !== undefined && linkReusable(link, Date.now()) ? link : undefined
    // `busy` stays set through the read of the old report and the upload after it.
    busy.current = true
    dispatch({ type: 'resend', link: reuse })
    if (reuse === undefined && link !== undefined && mayHaveLanded === true) {
      void landedOrUpload(now.photo, fix, place, link.reportId)
      return
    }
    void upload(now.photo, fix, place, reuse)
  }, [expire, landedOrUpload, upload])

  const checkAgain = useCallback(() => dispatch({ type: 'checkAgain', at: Date.now() }), [])

  // Sets the own pin from a result, if it makes one, and clears it 2 minutes later (spec §4.4).
  const keepOwnPin = useCallback((pin: OwnPin | undefined) => {
    if (pin === undefined) return
    clearTimeout(pinTimer.current)
    setOwnPin(pin)
    pinTimer.current = setTimeout(() => setOwnPin((now) => (now?.id === pin.id ? undefined : now)), OWN_PIN_LIFE_MS)
  }, [])

  const seenOnMap = useCallback((pins: readonly Pin[]) => {
    setOwnPin((now) => (now !== undefined && pins.some((pin) => pin.id === now.id) ? undefined : now))
  }, [])

  // The poll, while the wait is on. Coming back to the front polls at once, with the same absolute deadline, so the
  // 600 s never grows (C601, S5-R8); the schedule picks up where it was.
  const waiting = state.step === 'waiting' && !state.timedOut ? state : undefined
  const reportId = waiting?.reportId
  const pollWindow = waiting?.window
  const sent = waiting?.sent
  useEffect(() => {
    if (reportId === undefined || pollWindow === undefined || sent === undefined) return
    const mine = run.current
    let stop = new AbortController()
    const begin = () => {
      const signal = stop.signal
      const startElapsedMs = pollWindow.startElapsedMs + Math.max(0, Date.now() - pollWindow.startedAt)
      pollReport(apiUrl, reportId, { signal, deadlineAt: pollWindow.deadlineAt, startElapsedMs }).then(
        (result) => {
          if (signal.aborted || mine !== run.current) return
          dispatch({ type: 'result', result })
          keepOwnPin(ownPinOf(result, sent))
        },
        () => {
          // Past the deadline, or an answer that isn't a result: "No result yet", never a failure the server didn't
          // report (C601). An aborted poll was replaced or closed, and says nothing.
          if (signal.aborted || mine !== run.current) return
          dispatch({ type: 'timedOut' })
          // With the person on another screen, nobody waits here: the flow closes, so the position and the report id
          // go (Global Constraints). A published result still reaches the map.
          if (!onReportNow.current) close()
        },
      )
    }
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return
      stop.abort()
      stop = new AbortController()
      begin()
    }
    begin()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      stop.abort()
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [apiUrl, reportId, pollWindow, sent, keepOwnPin, close])

  // The photo goes when its 15 minutes pass, wherever the flow waits with it. An upload under way finishes first.
  const heldPhoto = state.step === 'place' || state.step === 'problem' ? state.photo : undefined
  useEffect(() => {
    if (heldPhoto === undefined) return
    const left = Date.parse(heldPhoto.capturedAt) + PHOTO_LIFE_MS - Date.now()
    const timer = setTimeout(expire, Number.isFinite(left) ? Math.max(0, left) : 0)
    return () => clearTimeout(timer)
  }, [heldPhoto, expire])

  // Leaving the report screen closes it, unless an upload or a wait is under way. A result that comes while the
  // person is away waits until they come back and leave again.
  const wasOnReport = useRef(onReport)
  useEffect(() => {
    const left = wasOnReport.current && !onReport
    wasOnReport.current = onReport
    if (left && !survivesLeaving(latest.current)) close()
  }, [onReport, close])

  // Nothing outlives the provider.
  useEffect(
    () => () => {
      fixStop.current?.abort()
      clearTimeout(pinTimer.current)
    },
    [],
  )

  const flow = useMemo<ReportFlow>(
    () => ({ state, start, streamOpened, photoTaken, retryFix, send, retry, checkAgain }),
    [state, start, streamOpened, photoTaken, retryFix, send, retry, checkAgain],
  )
  const own = useMemo<OwnPinState>(() => ({ pin: ownPin, seenOnMap }), [ownPin, seenOnMap])

  return (
    <FlowContext value={flow}>
      <OwnPinContext value={own}>{children}</OwnPinContext>
    </FlowContext>
  )
}

export function useReportFlow(): ReportFlow {
  const flow = useContext(FlowContext)
  if (flow === null) throw new Error('useReportFlow needs a <ReportFlowProvider> above it')
  return flow
}

function useOwnPinState(): OwnPinState {
  const own = useContext(OwnPinContext)
  if (own === null) throw new Error('useOwnPin needs a <ReportFlowProvider> above it')
  return own
}

// The person's own new pin, for the map (Task 13's mergeOwnPin), or undefined.
export function useOwnPin(): OwnPin | undefined {
  return useOwnPinState().pin
}

// For the map, with the pins it fetched from GET /map/pins: the own pin goes once they hold its id.
export function useSeenOnMap(): (pins: readonly Pin[]) => void {
  return useOwnPinState().seenOnMap
}
