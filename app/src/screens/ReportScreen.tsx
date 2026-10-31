import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { PausedNotice, ResultCard } from '../components/ResultCard'
import { T } from '../i18n'
import type { StringKey } from '../i18n/en'
import { useGate } from '../lib/consent'
import { focusFell } from '../lib/focus'
import { qualityRefusal } from '../lib/quality'
import { retryKind, type FlowState, type RefusedCode } from '../report/flow'
import { useReportFlow, type ReportFlow } from '../report/ReportFlowProvider'
import { routeHash } from '../router'
import { CameraStep } from './report/CameraStep'
import { CheckStep } from './report/CheckStep'
import { PlaceStep, type Place } from './report/PlaceStep'
import { WaitingStep } from './report/WaitingStep'

// Pressing a control fills it with ink and turns its text to the page's colour (S5-R6), as on the camera's view.
const PRESSED = 'enabled:active:border-ink enabled:active:bg-ink enabled:active:text-surface'
const BUTTON = `min-h-tap min-w-tap rounded-control border px-4 font-bold ${PRESSED}`
const PRIMARY = `${BUTTON} border-action bg-action text-on-action`
const LINK = 'inline-flex min-h-tap min-w-tap items-center text-action underline underline-offset-4'

const REFUSED_LINE: Record<RefusedCode, StringKey> = {
  capture_too_old: 'report.tooOld',
  capture_in_future: 'report.refused.capture_in_future',
  gps_too_coarse: 'report.refused.gps_too_coarse',
  nudge_too_far: 'report.refused.nudge_too_far',
  device_limit: 'report.limit.device_limit',
  global_cap: 'report.limit.global_cap',
}

// The report screen: the flow from photo to result (MS5 Task 12), one step at a time, inside the layout's <main>, so
// the screen line stays in view above every step; no step is a dialog or fullscreen. App wraps it in <NoticeGate>,
// so a typed #/report meets the consent notice first (C605). A build with no API address refuses here, before the
// camera, and uploads nothing.
export function ReportScreen({ apiUrl }: { apiUrl: string }) {
  if (apiUrl === '') {
    return (
      <section>
        <h1 className="text-title font-bold">
          <T k="nav.report" />
        </h1>
        <p className="mt-3 max-w-prose">
          <T k="report.noApi" />
        </p>
      </section>
    )
  }
  return <Flow />
}

// Which view shows, so focus can follow a change of view.
function viewOf(state: FlowState): string {
  switch (state.step) {
    case 'camera':
      return `camera:${state.shot}`
    case 'place':
      return state.photo === undefined ? 'place:old' : `place:${state.fix.status}:${'gen' in state.fix ? state.fix.gen : 0}`
    case 'waiting':
      return state.timedOut ? 'waiting:none' : 'waiting'
    case 'problem':
      return `problem:${state.problem.kind}:${state.photo === undefined ? 'old' : 'kept'}`
    default:
      return state.step
  }
}

function Flow() {
  const flow = useReportFlow()
  // The notice is checked again before any upload: the press runs only once it is accepted (C605). With storage
  // blocked, the gate asks each time rather than letting a photo go without it.
  const gate = useGate('notice')
  const box = useRef<HTMLDivElement>(null)
  const { state } = flow
  // The phone's quality check (C604) stands in front of the place step until the person picks "Send anyway" for this
  // photo (its shot). The location watch goes on underneath, and the photo's 15 minutes run as before.
  const [sendAnyway, setSendAnyway] = useState<number>()
  const checking =
    state.step === 'place' &&
    state.photo?.quality !== undefined &&
    qualityRefusal(state.photo.quality) !== null &&
    sendAnyway !== state.shot
  const view = checking ? `check:${state.shot}` : viewOf(state)

  // A new step replaces the control that was pressed, and focus would fall to the page: it goes to the step's
  // heading, where a screen reader starts reading (after the notice's "Continue" too, S5-R10). Focus that is
  // somewhere already stays there.
  useEffect(() => {
    if (!focusFell()) return
    const heading = box.current?.querySelector('h1')
    if (heading === null || heading === undefined) return
    heading.tabIndex = -1
    heading.focus({ preventScroll: true })
  }, [view])

  const send = (place: Place) => gate(() => flow.send(place))
  const retry = () => gate(() => flow.retry())

  return (
    <div ref={box} className="contents [&_h1]:outline-none">
      {checking && state.step === 'place' && state.photo?.quality !== undefined ? (
        <CheckStep
          scores={state.photo.quality}
          smallStill={state.photo.smallStill}
          onRetake={flow.start}
          onSend={() => setSendAnyway(state.shot)}
        />
      ) : (
        <Step state={state} flow={flow} onSend={send} onRetry={retry} />
      )}
    </div>
  )
}

function Step({
  state,
  flow,
  onSend,
  onRetry,
}: {
  state: FlowState
  flow: ReportFlow
  onSend(place: Place): void
  onRetry(): void
}) {
  switch (state.step) {
    case 'camera':
      // A fresh camera for each photo: Task 9's view closes itself at the shutter.
      return <CameraStep key={state.shot} onPhoto={flow.photoTaken} onStreamOpen={flow.streamOpened} />
    case 'place':
      return <PlaceView state={state} flow={flow} onSend={onSend} />
    // A key per phase: the heading is a new element when the photo is sent, so focus moves to it and a screen reader
    // says so.
    case 'sending':
      return <WaitingStep key="sending" phase="sending" />
    case 'waiting':
      return (
        <WaitingStep
          key="waiting"
          phase="waiting"
          uploadedAt={state.uploadedAt}
          timedOut={state.timedOut}
          onCheckAgain={flow.checkAgain}
        />
      )
    case 'result':
      return <ResultView state={state} onNewPhoto={flow.start} />
    case 'problem':
      return <ProblemView state={state} flow={flow} onRetry={onRetry} />
  }
}

// A step of this screen with its own heading.
function Section({ title, children }: { title: StringKey; children: ReactNode }) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="flex flex-col">
      <h1 id={headingId} className="text-title font-bold">
        <T k={title} />
      </h1>
      {children}
    </section>
  )
}

function NewPhoto({ onClick, link = false }: { onClick(): void; link?: boolean }) {
  return (
    <button type="button" onClick={onClick} className={link ? `${LINK} cursor-pointer` : PRIMARY}>
      <T k="report.newPhoto" />
    </button>
  )
}

// The 15 minutes have passed, so this photo can't be sent (C635; MS4's capture_too_old).
function TooOld({ onNewPhoto }: { onNewPhoto(): void }) {
  return (
    <>
      <p className="mt-3 max-w-prose">
        <T k="report.tooOld" />
      </p>
      <div className="mt-4">
        <NewPhoto onClick={onNewPhoto} />
      </div>
    </>
  )
}

// C602: a still under 1,600 px on its longer side may be too small to read. It can still be sent. It sits under the
// step's heading, so it is read after it.
function SmallStill({ onNewPhoto }: { onNewPhoto(): void }) {
  return (
    <div className="mt-3 max-w-prose rounded-control border border-dashed border-outline p-3">
      <p className="text-small">
        <T k="report.smallStill" />
      </p>
      <NewPhoto onClick={onNewPhoto} link />
    </div>
  )
}

// The pin, once the photo is in hand: finding the location, its problem, or the place step itself (Task 11).
function PlaceView({
  state,
  flow,
  onSend,
}: {
  state: Extract<FlowState, { step: 'place' }>
  flow: ReportFlow
  onSend(place: Place): void
}) {
  const { photo, fix } = state
  if (photo === undefined) {
    return (
      <Section title="report.notSent">
        <TooOld onNewPhoto={flow.start} />
      </Section>
    )
  }
  const small = photo.smallStill ? <SmallStill onNewPhoto={flow.start} /> : null
  if (fix.status === 'found') {
    // A key per fix, so a retried fix starts a fresh place step.
    return <PlaceStep key={fix.gen} fix={fix.fix} notice={small} onSend={onSend} onRetryFix={flow.retryFix} />
  }
  return (
    <Section title="report.locationTitle">
      {small}
      {fix.status === 'failed' ? (
        <div role="alert" className="mt-3 max-w-prose">
          <p>
            <T k={fix.line} />
          </p>
          <button type="button" onClick={flow.retryFix} className={`${PRIMARY} mt-4`}>
            <T k="location.retry" />
          </button>
        </div>
      ) : (
        <p role="status" className="mt-3 max-w-prose">
          <T k="report.locating" />
        </p>
      )}
    </Section>
  )
}

// Links to the screens that still work, for a limit, where a retry now would end the same way.
function StillWorks() {
  return (
    <ul className="mt-1 flex flex-wrap gap-x-6">
      <li>
        <a href={routeHash({ name: 'map' })} className={LINK}>
          <T k="nav.map" />
        </a>
      </li>
      <li>
        <a href={routeHash({ name: 'tested' })} className={LINK}>
          <T k="nav.tested" />
        </a>
      </li>
    </ul>
  )
}

// Why the photo wasn't sent, and what can be done. Every line here is the app's own, never "Processing failed":
// nothing was analysed (C638).
function ProblemView({
  state,
  flow,
  onRetry,
}: {
  state: Extract<FlowState, { step: 'problem' }>
  flow: ReportFlow
  onRetry(): void
}) {
  const { problem, photo } = state
  const retry = retryKind(problem)
  const nothing = (
    <p className="mt-2">
      <T k="report.nothingUploaded" />
    </p>
  )

  let body: ReactNode
  if (problem.kind === 'paused') {
    body = <PausedNotice links={['map', 'tested']}>{nothing}</PausedNotice>
  } else if (problem.kind === 'upload') {
    // The connection is named only when the browser said it was offline; any other failure gets the neutral line. No
    // "Nothing was uploaded." here: a photo whose upload timed out may have reached S3.
    body = (
      <p role="alert">
        <T k={problem.offline === true ? 'report.uploadFailed' : 'report.sendFailed'} />
      </p>
    )
  } else {
    body = (
      <div role="alert">
        <p>
          <T k={problem.kind === 'refused' ? REFUSED_LINE[problem.code] : 'report.sendFailed'} />
        </p>
        {nothing}
        {retry === 'none' && <StillWorks />}
      </div>
    )
  }

  // A resend (after an upload problem or a pause) or a new fix (after a location refusal) reuses the photo while it is
  // under 15 minutes old; past that, only a new photo. A limit has no retry; other refusals ask for a new photo.
  let action: ReactNode = null
  if (retry === 'resend' || retry === 'refix') {
    action =
      photo === undefined ? (
        <TooOld onNewPhoto={flow.start} />
      ) : (
        <div className="mt-4">
          <button type="button" onClick={retry === 'resend' ? onRetry : flow.retryFix} className={PRIMARY}>
            <T k={retry === 'resend' ? 'result.tryAgain' : 'location.retry'} />
          </button>
        </div>
      )
  } else if (retry === 'newPhoto') {
    action = (
      <div className="mt-4">
        <NewPhoto onClick={flow.start} />
      </div>
    )
  }

  return (
    <Section title="report.notSent">
      <div className="mt-3 max-w-prose">{body}</div>
      {action}
    </Section>
  )
}

// The person's own result (spec §4.2), with a link to the map and, after a reading or a refusal, a new photo. A
// failed result has the card's own "Try again", which also starts a new photo; a paused one has neither, and its
// card already links to the map.
function ResultView({ state, onNewPhoto }: { state: Extract<FlowState, { step: 'result' }>; onNewPhoto(): void }) {
  const { result, fixAccuracyM } = state
  const paused = result.status === 'failed' && result.refusalReason === 'model_calls_paused'
  const again = result.status === 'done' || result.status === 'refused'
  return (
    <Section title="report.resultTitle">
      <div className="mt-3">
        <ResultCard result={result} source="own" fixAccuracyM={fixAccuracyM} onNewPhoto={onNewPhoto} />
      </div>
      {!paused && (
        <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2">
          {again && <NewPhoto onClick={onNewPhoto} />}
          <a href={routeHash({ name: 'map' })} className={LINK}>
            <T k="nav.map" />
          </a>
        </div>
      )}
    </Section>
  )
}
