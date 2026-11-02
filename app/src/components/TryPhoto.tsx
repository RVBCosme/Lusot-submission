import { ImagePlusIcon, LoaderCircleIcon } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import { T, useT } from '../i18n'
import type { StringKey } from '../i18n/en'
import { HttpError, postToS3, requestTry, type ReportResult } from '../lib/api'
import { hasNotice, NOTICE_VERSION, useGate } from '../lib/consent'
import { getDeviceId } from '../lib/device'
import { focusFell } from '../lib/focus'
import { POLL, pollReport } from '../lib/poll'
import { retryOnce } from '../lib/retry'
import { photoToJpeg, TRY_TYPES, TryPhotoError } from '../lib/tryPhoto'
import { PausedNotice, ResultCard } from './ResultCard'

const BUTTON =
  'mt-3 inline-flex min-h-tap items-center gap-2 rounded-control bg-action px-4 font-bold text-on-action ' +
  'active:bg-ink active:text-surface'

// Where a chosen photo's run stands. Only this component holds it, so a report id never outlives the page.
type Run =
  | { phase: 'preparing' } // the file is being re-encoded
  | { phase: 'sending' } // POST /try, then the photo to S3
  | { phase: 'waiting' } // its own poll
  | { phase: 'noResult'; reportId: string } // the poll ran out: "No result yet" and "Check again" (C601)
  | { phase: 'result'; result: ReportResult }
  | { phase: 'paused' } // 503 uploads_paused or model_calls_paused (C638)
  | { phase: 'refused'; line: StringKey } // a limit: nothing ran
  | { phase: 'fileProblem'; line: 'try.unsupported' | 'try.unreadable' } // nothing was sent
  | { phase: 'sendFailed' } // any other failure before the photo reached S3

const inFlight = (run: Run | undefined) => run?.phase === 'preparing' || run?.phase === 'sending' || run?.phase === 'waiting'

// A card's stand-in result while there is none yet: the card shows "No result yet" for it (C601).
const NO_RESULT: ReportResult = { reportId: '', status: 'pending', mode: 'try', published: false }

const LIMITS: ReadonlySet<string> = new Set(['device_limit', 'global_cap', 'daily_cap'])

// What a failed POST /try means. Nothing was kept in any of these, so the person may choose again.
function afterRequestFailure(err: unknown): Run {
  if (err instanceof HttpError) {
    if (err.status === 503 && (err.code === 'uploads_paused' || err.code === 'model_calls_paused')) return { phase: 'paused' }
    if (err.status === 429 && err.code !== undefined && LIMITS.has(err.code)) {
      return { phase: 'refused', line: `try.limit.${err.code}` as StringKey }
    }
  }
  return { phase: 'sendFailed' }
}

// "Try your own photo" on the Tested page (C534, C640): the person chooses a photo from their device, which is re-encoded
// upright and without EXIF, sent through POST /try and read like a sample. The result shows only to them, in the same
// card, and never goes on the map. It is the one file input in the app. It passes the notice gate first, since the photo
// goes to Meta as a report's does.
export function TryPhoto({ apiUrl }: { apiUrl: string }) {
  const t = useT()
  const gate = useGate('notice')
  const [run, setRun] = useState<Run>()
  const field = useRef<HTMLInputElement>(null)
  const box = useRef<HTMLDivElement>(null)
  // A choice, between its change event and its outcome. A ref, so two change events in one tick start one run.
  const paying = useRef(false)
  // Whether the notice gate has let the picker open this visit: with storage blocked, hasNotice() can't say.
  const gated = useRef(false)
  // The poll, aborted when the page closes.
  const polling = useRef<AbortController | null>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      polling.current?.abort()
      polling.current = null
    }
  }, [])

  // The pressed button goes when the run starts, so focus would fall to the page: it moves to the status, where the run
  // is (C612's pattern). Only on a change, never when the page first shows.
  const phase = run?.phase
  const shown = useRef(phase)
  useEffect(() => {
    if (shown.current === phase) return
    shown.current = phase
    if (!focusFell()) return
    box.current?.focus({ preventScroll: true })
  }, [phase])

  // Ends the run, unless the page has closed.
  const finish = useCallback((next: Run) => {
    paying.current = false
    if (alive.current) setRun(next)
  }, [])

  // Polls the report (C601): the first poll's 600 s count from the upload, and "Check again" polls the same report for
  // another 600 s at the 15 s interval, and never uploads again.
  const watch = useCallback(
    (reportId: string, again: boolean) => {
      const controller = new AbortController()
      polling.current = controller
      paying.current = true
      setRun({ phase: 'waiting' })
      const end = (next: Run) => {
        if (controller.signal.aborted) return
        polling.current = null
        finish(next)
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
    [apiUrl, finish],
  )

  async function start(file: File) {
    setRun({ phase: 'preparing' })
    let jpeg: Blob
    try {
      jpeg = await photoToJpeg(file)
    } catch (err) {
      // A type Lusot doesn't read, or any other failure to prepare the photo (a decode, a canvas or an encode): the
      // photo is the problem, not the connection, and nothing was sent.
      const unsupported = err instanceof TryPhotoError && err.kind === 'unsupported'
      finish({ phase: 'fileProblem', line: unsupported ? 'try.unsupported' : 'try.unreadable' })
      return
    }
    if (!alive.current) return
    setRun({ phase: 'sending' })
    let link: Awaited<ReturnType<typeof requestTry>>
    try {
      link = await requestTry(apiUrl, NOTICE_VERSION, getDeviceId())
    } catch (err) {
      finish(afterRequestFailure(err))
      return
    }
    if (!alive.current) return
    try {
      // One more try on a failure on the way, as a report's upload has (C635). It reuses the same link, so the photo is
      // analysed and paid for once.
      await retryOnce(() => postToS3(link.upload, jpeg))
    } catch {
      finish({ phase: 'sendFailed' })
      return
    }
    if (!alive.current) return
    watch(link.reportId, false)
  }

  function chosen(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget
    const file = input.files?.[0]
    // Cleared at once, so choosing the same file again fires a change.
    input.value = ''
    // The gate comes first. A photo that arrives without the notice accepted (or the gate passed this visit, with
    // storage blocked) is dropped and nothing is sent.
    if (file === undefined || paying.current || !(gated.current || hasNotice())) return
    paying.current = true
    void start(file)
  }

  function choose() {
    gate(() => {
      gated.current = true
      field.current?.click()
    })
  }

  function checkAgain(reportId: string) {
    if (paying.current) return
    watch(reportId, true)
  }

  let body: ReactNode = null
  switch (run?.phase) {
    case 'preparing':
    case 'sending':
    case 'waiting':
      body = (
        <p role="status" className="mt-3 flex min-h-tap items-center gap-2 font-bold lg:max-w-prose">
          <LoaderCircleIcon aria-hidden="true" className="size-5 shrink-0 animate-spin motion-reduce:animate-none" />
          <T k="try.reading" />
        </p>
      )
      break
    case 'result':
      body = (
        <div className="mt-3">
          {/* No "Try again" on the card: "Choose another photo" below it is the one way on. */}
          <ResultCard result={run.result} source="try" />
        </div>
      )
      break
    case 'noResult': {
      const { reportId } = run
      body = (
        <div className="mt-3">
          <ResultCard result={NO_RESULT} source="try" noResultYet onCheckAgain={() => checkAgain(reportId)} />
        </div>
      )
      break
    }
    case 'paused':
      // The Tested page is where this is, so the paused line links to the map only (C638).
      body = (
        <div className="mt-3 lg:max-w-prose">
          <PausedNotice links={['map']} />
        </div>
      )
      break
    case 'refused':
    case 'fileProblem':
      body = (
        <p role="status" className="mt-3 lg:max-w-prose">
          <T k={run.line} />
        </p>
      )
      break
    case 'sendFailed':
      body = (
        <p role="status" className="mt-3 lg:max-w-prose">
          <T k="try.sendFailed" />
        </p>
      )
      break
  }

  if (apiUrl === '') {
    return (
      <p className="mt-4 lg:max-w-prose">
        <T k="try.noApi" />
      </p>
    )
  }

  const label = t('try.inputLabel')
  return (
    <div ref={box} tabIndex={-1} className="outline-none">
      {/* The one file input in the app (C640). It is out of sight, out of the tab order and out of the accessibility
          tree, since only the button opens it, after the notice gate: a screen reader that could activate the input
          would open the picker with no gate. */}
      <input
        ref={field}
        type="file"
        accept={TRY_TYPES.join(',')}
        aria-hidden="true"
        aria-label={label.text}
        lang={label.lang}
        tabIndex={-1}
        onChange={chosen}
        className="sr-only"
      />
      {body}
      {!inFlight(run) && (
        <button type="button" onClick={choose} className={BUTTON}>
          <ImagePlusIcon aria-hidden="true" className="size-5 shrink-0" />
          <T k={run === undefined ? 'try.choose' : 'try.chooseAnother'} />
        </button>
      )}
    </div>
  )
}
