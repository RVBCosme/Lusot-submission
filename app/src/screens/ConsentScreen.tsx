import { useEffect, useRef, useState } from 'react'
import { Markdown } from '../components/Markdown'
import consentText from '../content/consent.en.md?raw'
import { T } from '../i18n'

export type GateKind = 'adult' | 'notice'

// Pressing a control fills it with ink and turns its text to the page's colour, a pair far above 4.5:1 in both
// themes, rather than fading it (S5-R6).
const PRESSED = 'enabled:active:border-ink enabled:active:bg-ink enabled:active:text-surface'
const BUTTON = `min-h-tap min-w-tap rounded-control border px-4 font-bold ${PRESSED}`

// The gates' screen (C605), drawn inside the layout's <main>, so the screen-line bar stays on top of it. `notice`
// is Window 4's consent notice with the 18+ check; `adult` is the 18+ check alone, before a sample. The notice's
// prose is consent.en.md; its checkbox, buttons and link are real controls here, and "Not affiliated with MMDA."
// comes from the string table. Taglish shows the notice's English text until Rene approves its Taglish (C619).
export function ConsentScreen({
  kind,
  onContinue,
  onCancel,
}: {
  kind: GateKind
  onContinue: () => void
  onCancel: () => void
}) {
  const [adult, setAdult] = useState(false)
  const root = useRef<HTMLElement>(null)

  // The screen replaces what was there, so focus moves to its heading, where a screen reader starts reading. The
  // heading isn't a control, so it draws no focus ring; the next Tab reaches the checkbox, which does.
  useEffect(() => {
    const heading = root.current?.querySelector('h1')
    if (heading === null || heading === undefined) return
    heading.tabIndex = -1
    heading.focus()
  }, [])

  return (
    <section ref={root} className="max-w-prose [&_h1]:outline-none">
      {kind === 'notice' ? (
        <Markdown source={consentText} lang="en" testId="notice" />
      ) : (
        <>
          <h1 className="text-title font-bold">
            <T k="consent.adultTitle" />
          </h1>
          <p className="mt-3">
            <T k="consent.adultBody" />
          </p>
        </>
      )}
      <label className="mt-6 flex min-h-tap cursor-pointer items-center gap-3 rounded-control border border-outline px-3 py-2">
        <input
          type="checkbox"
          checked={adult}
          onChange={(event) => setAdult(event.target.checked)}
          className="size-6 shrink-0 cursor-pointer accent-action"
        />
        <span>
          <T k="consent.adult" />{' '}
          <span className="text-ink-2">
            <T k="consent.required" />
          </span>
        </span>
      </label>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          disabled={!adult}
          onClick={() => {
            if (adult) onContinue()
          }}
          className={`${BUTTON} border-action bg-action text-on-action disabled:cursor-not-allowed disabled:opacity-50`}
        >
          <T k="consent.continue" />
        </button>
        <button type="button" onClick={onCancel} className={`${BUTTON} border-outline`}>
          <T k="consent.notNow" />
        </button>
      </div>
      <p className="mt-4">
        <a href="#/privacy" className="inline-flex min-h-tap min-w-tap items-center text-action underline underline-offset-4">
          <T k="consent.readPolicy" />
        </a>
      </p>
      <p className="mt-2 text-small text-ink-2">
        <T k="about.notAffiliated" />
      </p>
    </section>
  )
}
