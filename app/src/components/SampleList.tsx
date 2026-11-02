import { LoaderCircleIcon } from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Line, T, useLanguage, useT } from '../i18n'
import type { StringKey } from '../i18n/en'
import { LEVELS } from '../copy/levels'
import { getSamples, HttpError, runSample, type ReportResult, type Sample, type SavedSample } from '../lib/api'
import { useGate } from '../lib/consent'
import { creditStatesChange } from '../lib/credit'
import { getDeviceId } from '../lib/device'
import { POLL, pollReport } from '../lib/poll'
import { focusFell } from '../lib/focus'
import { photoDateLine } from '../lib/time'
import { PausedNotice, ResultCard } from './ResultCard'

// "Short", for amendment 11: fewer than 3 samples. A short or empty list, or one that couldn't be read, says more are
// coming, and never shows an error.
const SHORT_LIST = 3
// A photo link lasts 5 minutes (MS4's C512). A photo that fails to load asks for fresh links, at most once a minute.
const LINK_REFRESH_MS = 60_000

const BUTTON =
  'mt-3 inline-flex min-h-tap items-center rounded-control bg-action px-4 font-bold text-on-action ' +
  'enabled:active:bg-ink enabled:active:text-surface disabled:cursor-not-allowed disabled:opacity-50'

// Where one sample's run stands. Only this screen holds it, so a report id never outlives the page (spec §4.4).
type Run =
  | { phase: 'starting' } // POST /samples/{id} sent, no answer yet
  | { phase: 'waiting' } // its own poll
  | { phase: 'noResult'; reportId: string } // the poll ran out: "No result yet" and "Check again" (C601)
  | { phase: 'result'; result: ReportResult }
  | { phase: 'saved'; result: ReportResult; savedAt: string } // model calls paused: the seeding run's result (C617)
  | { phase: 'paused' } // MS1's 503 uploads_paused (C638)
  | { phase: 'refused'; line: StringKey } // a limit, a sample gone: nothing ran
  | { phase: 'unanswered' } // no usable answer: a paid run may have started (S5-R8)
  | { phase: 'failed' } // the server said no before any run, so the person may try again

const inFlight = (run: Run | undefined) => run?.phase === 'starting' || run?.phase === 'waiting'
// A sample's button shows before any run, and again only after a refusal that started nothing and may pass next time:
// a plain refusal, or MS1's 503 uploads_paused, since MS4 checks that switch before any run and it can come back off
// (C638, as an upload's "Try again" stays).
const runnable = (run: Run | undefined) => run === undefined || run.phase === 'failed' || run.phase === 'paused'
// It shows under the card too when the server reported the run failed, as the card's "Processing failed, try again."
// asks: a new run is a new report, paid once (M4). A paused run reads as a pause, never a failure (C638), so not then.
const failedRun = (run: Run | undefined) =>
  run?.phase === 'result' && run.result.status === 'failed' && run.result.refusalReason !== 'model_calls_paused'

// A card's stand-in result while there is none yet: the card shows "No result yet" for it (C601).
const NO_RESULT: ReportResult = { reportId: '', status: 'pending', mode: 'sample', published: false }

const KNOWN_LEVELS: ReadonlySet<unknown> = new Set(LEVELS)

// MS4's saved answer (C527, amendment 10) as a result the card can show, or undefined when it can't be shown truly: no
// date, or a done result with neither "no flood seen" nor one of the 9 levels. It never carries a report id.
function savedResultOf({ savedAt, result }: SavedSample): ReportResult | undefined {
  if (typeof savedAt !== 'string' || !Number.isFinite(Date.parse(savedAt))) return undefined
  if (typeof result !== 'object' || result === null) return undefined
  const readable =
    result.status === 'refused' ||
    (result.status === 'done' && (result.noFloodSeen === true || KNOWN_LEVELS.has(result.level)))
  if (!readable) return undefined
  return { ...result, reportId: '', mode: 'sample', published: false }
}

// What a failed POST /samples/{id} means. runSample is never retried (Task 5): a run whose answer was lost may already
// be paid for, so a timeout, a lost connection, an answer in the wrong shape or a server error reads as "may have
// started". MS4 checks the uploads switch, the id and the limits before it starts a run, so those refusals cost nothing.
function afterFailure(err: unknown): Run {
  if (!(err instanceof HttpError)) return { phase: 'unanswered' }
  if (err.status === 503 && err.code === 'uploads_paused') return { phase: 'paused' }
  if (err.status === 429 && err.code === 'device_limit') return { phase: 'refused', line: 'sample.limit.device_limit' }
  if (err.status === 429 && err.code === 'global_cap') return { phase: 'refused', line: 'sample.limit.global_cap' }
  // MS4's C534: the day's cap on paid sample runs, shared with the chosen photos.
  if (err.status === 429 && err.code === 'daily_cap') return { phase: 'refused', line: 'sample.limit.daily_cap' }
  if (err.status === 404) return { phase: 'refused', line: 'sample.gone' }
  if (err.status >= 500) return { phase: 'unanswered' }
  return { phase: 'failed' }
}

// The samples on the Tested page (C617): each credited photo, blurred, with its place, date, event and credit line, and
// "Run this sample", which spends Meta credits. A run passes the 18+ check, makes one POST /samples/{id}, then polls
// its own report and shows the result card with the Sample badge. It never goes through the report flow, whose notice
// gate would hide the result from someone who passed only the 18+ check, and it never sets the own pin.
export function SampleList({ apiUrl }: { apiUrl: string }) {
  // undefined while the list loads; a list that couldn't be read is an empty one.
  const [samples, setSamples] = useState<Sample[]>()
  const [runs, setRuns] = useState<Record<string, Run>>({})
  const gate = useGate('adult')
  // The sample whose paid run is between its tap and its outcome. A ref, so two taps in one tick start one run.
  const paying = useRef<string | null>(null)
  // Each sample's poll, aborted when the page closes.
  const polls = useRef(new Map<string, AbortController>())
  const alive = useRef(true)
  const linksReadAt = useRef(0)

  useEffect(() => {
    alive.current = true
    const open = polls.current
    return () => {
      alive.current = false
      for (const controller of open.values()) controller.abort()
      open.clear()
    }
  }, [])

  useEffect(() => {
    if (apiUrl === '') return
    let live = true
    linksReadAt.current = Date.now()
    getSamples(apiUrl).then(
      (list) => {
        if (live) setSamples(list)
      },
      () => {
        if (live) setSamples([])
      },
    )
    return () => {
      live = false
    }
  }, [apiUrl])

  const setRun = useCallback((id: string, run: Run) => setRuns((now) => ({ ...now, [id]: run })), [])

  // Polls the sample's report (C601). The first poll's 600 s count from the run's start, as an absolute deadline
  // (Task 5); "Check again" polls the same report for another 600 s at the 15 s interval, and never runs it again.
  const poll = useCallback(
    (id: string, reportId: string, again: boolean) => {
      const controller = new AbortController()
      polls.current.set(id, controller)
      setRun(id, { phase: 'waiting' })
      const end = (run: Run) => {
        if (controller.signal.aborted) return
        polls.current.delete(id)
        if (paying.current === id) paying.current = null
        setRun(id, run)
      }
      pollReport(apiUrl, reportId, {
        signal: controller.signal,
        startElapsedMs: again ? POLL.midForMs : 0,
        deadlineAt: Date.now() + POLL.windowMs,
      }).then(
        (result) => end({ phase: 'result', result }),
        // Past the deadline, or an answer that isn't a result: "No result yet", never a failure the server didn't report.
        () => end({ phase: 'noResult', reportId }),
      )
    },
    [apiUrl, setRun],
  )

  async function start(id: string) {
    setRun(id, { phase: 'starting' })
    let answer: Awaited<ReturnType<typeof runSample>>
    try {
      answer = await runSample(apiUrl, id, getDeviceId())
    } catch (err) {
      paying.current = null
      if (alive.current) setRun(id, afterFailure(err))
      return
    }
    if (!alive.current) return
    if ('saved' in answer) {
      // Model calls are paused, so nothing ran and nothing is polled: the saved reading, or a plain line for an answer
      // the card can't show.
      paying.current = null
      const result = savedResultOf(answer)
      setRun(id, result === undefined ? { phase: 'failed' } : { phase: 'saved', result, savedAt: answer.savedAt })
      return
    }
    poll(id, answer.reportId, false)
  }

  function run(id: string) {
    gate(() => {
      if (paying.current !== null) return
      paying.current = id
      void start(id)
    })
  }

  function checkAgain(id: string, reportId: string) {
    if (polls.current.has(id)) return
    poll(id, reportId, true)
  }

  // Fresh photo links for the samples already listed; the list itself, and every run, stay as they are.
  const refreshLinks = useCallback(() => {
    if (apiUrl === '' || Date.now() - linksReadAt.current < LINK_REFRESH_MS) return
    linksReadAt.current = Date.now()
    getSamples(apiUrl).then(
      (fresh) => {
        if (!alive.current) return
        const links = new Map(fresh.map((sample) => [sample.sampleId, sample.photoUrl]))
        setSamples((now) =>
          now?.map((sample) =>
            links.has(sample.sampleId) ? { ...sample, photoUrl: links.get(sample.sampleId) } : sample,
          ),
        )
      },
      () => {},
    )
  }, [apiUrl])

  if (apiUrl === '') {
    return (
      <p className="mt-4">
        <T k="tested.samples.noApi" />
      </p>
    )
  }
  if (samples === undefined) {
    return (
      <p role="status" className="mt-4 text-ink-2">
        <T k="tested.samples.loading" />
      </p>
    )
  }
  const busy = Object.values(runs).some(inFlight)
  return (
    <>
      {samples.length > 0 && (
        <ul className="mt-4 space-y-10">
          {samples.map((sample) => {
            const id = sample.sampleId
            const state = runs[id]
            return (
              <SampleItem
                key={id}
                sample={sample}
                run={state}
                busy={busy}
                onRun={() => run(id)}
                onCheckAgain={() => {
                  if (state?.phase === 'noResult') checkAgain(id, state.reportId)
                }}
                onPhotoExpired={refreshLinks}
              />
            )
          })}
        </ul>
      )}
      {samples.length < SHORT_LIST && (
        <p className="mt-4">
          <T k="tested.samples.more" />
        </p>
      )}
    </>
  )
}

function SampleItem({
  sample,
  run,
  busy,
  onRun,
  onCheckAgain,
  onPhotoExpired,
}: {
  sample: Sample
  run: Run | undefined
  busy: boolean
  onRun(): void
  onCheckAgain(): void
  onPhotoExpired(): void
}) {
  const box = useRef<HTMLDivElement>(null)
  const captionId = useId()

  // The pressed button goes when the run starts, and the preview when its card comes, so focus would fall to the page:
  // it moves to the sample, where its status is (C612's pattern). Only on a change, never when the list first shows.
  const phase = run?.phase
  const shown = useRef(phase)
  useEffect(() => {
    if (shown.current === phase) return
    shown.current = phase
    if (!focusFell()) return
    box.current?.focus({ preventScroll: true })
  }, [phase])

  let body: ReactNode
  if (run?.phase === 'result') {
    body = (
      <>
        <ResultCard result={run.result} source="sample" sample={sample} onPhotoExpired={onPhotoExpired} />
        {failedRun(run) && (
          <button type="button" disabled={busy} onClick={onRun} className={BUTTON}>
            <T k="sample.run" />
          </button>
        )}
      </>
    )
  } else if (run?.phase === 'saved') {
    // The card puts the paused line first, marks the reading "Saved result from" its date, and says it is a saved
    // reading, with no basis, overlay or inches (C617, MS9's N2).
    body = (
      <ResultCard
        result={run.result}
        source="sample"
        sample={sample}
        savedAt={run.savedAt}
        onPhotoExpired={onPhotoExpired}
      />
    )
  } else if (run?.phase === 'noResult') {
    body = (
      <ResultCard
        result={NO_RESULT}
        source="sample"
        sample={sample}
        noResultYet
        onCheckAgain={onCheckAgain}
        onPhotoExpired={onPhotoExpired}
      />
    )
  } else {
    body = (
      <>
        <Preview sample={sample} captionId={captionId} onPhotoError={onPhotoExpired} />
        {runnable(run) ? (
          <>
            {run?.phase === 'failed' && (
              <p role="status" className="mt-3">
                <T k="sample.failed" />
              </p>
            )}
            {run?.phase === 'paused' && (
              // The Tested page is where this is, so the paused line links to the map only (C638).
              <div className="mt-3">
                <PausedNotice links={['map']} />
              </div>
            )}
            <button type="button" disabled={busy} aria-describedby={captionId} onClick={onRun} className={BUTTON}>
              <T k="sample.run" />
            </button>
          </>
        ) : (
          <RunStatus run={run} />
        )}
      </>
    )
  }

  return (
    <li>
      <div ref={box} tabIndex={-1} className="outline-none">
        {body}
      </div>
    </li>
  )
}

// The sample's photo, blurred, with its date, place and event, its credit line and what Lusot changed (C617, C637). A
// credit that already says the photo was blurred states the change, so the line is left out then.
function Preview({ sample, captionId, onPhotoError }: { sample: Sample; captionId: string; onPhotoError(): void }) {
  const t = useT()
  const { lang } = useLanguage()
  const from = photoDateLine(t, lang, { date: sample.date, place: sample.place, event: sample.event })
  const alt = t('sample.photoAlt')
  return (
    <figure>
      {sample.photoUrl !== undefined && (
        <img
          src={sample.photoUrl}
          alt={alt.text}
          lang={alt.lang}
          loading="lazy"
          onError={() => onPhotoError()}
          className="w-full rounded-control border border-outline"
        />
      )}
      <figcaption id={captionId} className="mt-2 text-small text-ink-2">
        {from !== undefined && (
          <p className="text-body font-bold text-ink">
            <Line value={from} />
          </p>
        )}
        <p className="mt-1">
          <Line value={{ text: sample.credit, lang: 'en' }} />
        </p>
        {!creditStatesChange(sample.credit) && (
          <p className="mt-1">
            <T k="sample.edited" />
          </p>
        )}
      </figcaption>
    </figure>
  )
}

// Where a run stands, below its preview: under way, refused, or unanswered.
function RunStatus({ run }: { run: Run | undefined }) {
  switch (run?.phase) {
    case 'starting':
    case 'waiting':
      return (
        <p role="status" className="mt-3 flex min-h-tap items-center gap-2 font-bold">
          <LoaderCircleIcon aria-hidden="true" className="size-5 shrink-0 animate-spin motion-reduce:animate-none" />
          <T k="sample.reading" />
        </p>
      )
    case 'refused':
      return (
        <p role="status" className="mt-3">
          <T k={run.line} />
        </p>
      )
    case 'unanswered':
      return (
        <p role="status" className="mt-3">
          <T k="sample.unanswered" />
        </p>
      )
    default:
      return null
  }
}
