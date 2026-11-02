import { RotateCcwIcon } from 'lucide-react'
import { useId } from 'react'
import { T } from '../../i18n'
import { qualityRefusal, type QualityScores } from '../../lib/quality'

// Pressing a control fills it with ink and turns its text to the page's colour (S5-R6), as elsewhere in the flow.
const PRESSED = 'enabled:active:border-ink enabled:active:bg-ink enabled:active:text-surface'
const BUTTON = `min-h-tap min-w-tap rounded-control border px-4 font-bold ${PRESSED}`
const PRIMARY = `${BUTTON} inline-flex items-center justify-center gap-2 border-action bg-action text-on-action`
const SECONDARY = `${BUTTON} border-outline`

// The phone's quality check (C604, Task 10): a photo the server would call too dark or too blurry gets the retake
// tip, with "Retake" first and "Send anyway" second. It only warns: "Send anyway" goes on with this photo, and the
// server checks again for free. With a small still, the small-photo warning shows too (C602).
export function CheckStep({
  scores,
  smallStill,
  onRetake,
  onSend,
}: {
  scores: QualityScores
  smallStill: boolean
  onRetake(): void
  onSend(): void
}) {
  const headingId = useId()
  const refusal = qualityRefusal(scores)
  return (
    <section aria-labelledby={headingId} className="flex flex-col">
      <h1 id={headingId} className="text-title font-bold">
        <T k="report.checkTitle" />
      </h1>
      <div role="status" className="mt-3 max-w-prose space-y-2">
        {refusal !== null && (
          <p className="font-bold">
            <T k={refusal === 'too_dark' ? 'retake.too_dark' : 'retake.too_blurry'} />
          </p>
        )}
        {smallStill && (
          <p className="text-small">
            <T k="report.smallStill" />
          </p>
        )}
        <p className="text-small text-ink-2">
          <T k="report.checkNote" />
        </p>
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={onRetake} className={PRIMARY}>
          <RotateCcwIcon aria-hidden="true" className="size-5 shrink-0" />
          <T k="report.retake" />
        </button>
        <button type="button" onClick={onSend} className={SECONDARY}>
          <T k="report.sendAnyway" />
        </button>
      </div>
    </section>
  )
}
