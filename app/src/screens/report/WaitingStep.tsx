import { useEffect, useId, useState } from 'react'
import { ResultCard } from '../../components/ResultCard'
import { T } from '../../i18n'
import type { ReportResult } from '../../lib/api'
import { QUEUE_NOTE_AFTER_MS } from '../../report/flow'

// What the card is handed to say "No result yet": the app's own state (C601), with no report id and no status the
// server gave.
const NO_RESULT: ReportResult = { reportId: '', status: 'pending', mode: 'live', published: false }

type Props = { phase: 'sending' } | { phase: 'waiting'; uploadedAt: number; timedOut: boolean; onCheckAgain(): void }

// The report flow's wait (C601, C635): sending the photo, then the seconds since it was sent while Lusot reads it.
// It never shows a failure the server hasn't reported: when the poll runs out, the card says "No result yet" and
// "Check again" polls the same report. The person may leave; the wait goes on and the result waits here.
export function WaitingStep(props: Props) {
  const headingId = useId()
  const busy = props.phase === 'sending' || !props.timedOut
  return (
    <section aria-labelledby={headingId} aria-busy={busy} className="flex flex-col">
      <h1 id={headingId} className="text-title font-bold">
        <T k={props.phase === 'sending' ? 'report.sendingTitle' : 'report.waitingTitle'} />
      </h1>
      {props.phase === 'sending' ? (
        <p role="status" className="mt-2 max-w-prose">
          <T k="report.sendingHint" />
        </p>
      ) : props.timedOut ? (
        <div className="mt-3">
          <ResultCard result={NO_RESULT} source="own" noResultYet onCheckAgain={props.onCheckAgain} />
        </div>
      ) : (
        <Elapsed since={props.uploadedAt} />
      )}
    </section>
  )
}

// The seconds since the upload, read once a second. They are not a live region, so a screen reader isn't told every
// second; the note that other photos may be ahead is, once, when it appears at 60 s. It promises no time.
function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  const elapsedMs = Math.max(0, now - since)
  return (
    <>
      <p className="mt-2 max-w-prose">
        <T k="report.waitingHint" />
      </p>
      <p className="mt-6 border-l-4 border-outline pl-3 text-heading font-bold tabular-nums">
        <T k="report.elapsed" vars={{ seconds: Math.floor(elapsedMs / 1000) }} />
      </p>
      <div role="status" className="mt-3 max-w-prose">
        {elapsedMs >= QUEUE_NOTE_AFTER_MS && (
          <p>
            <T k="report.queue" />
          </p>
        )}
      </div>
    </>
  )
}
