import { useEffect, useId, useRef } from 'react'
import { T } from '../i18n'
import { ScreenLine } from '../layout/ScreenLine'

// The same fill-with-ink press as the rest of the app's buttons (S5-R6).
const BUTTON =
  'min-h-tap min-w-tap rounded-control border-2 border-outline px-4 font-bold active:border-ink active:bg-ink active:text-surface'

// The flag's question (C613), in a dialog of the app's own: never the browser's confirm. It is a modal <dialog>, which
// the browser puts in its top layer, over the layout's bar. So it carries its own screen line (S5-R5), and the person
// sees the line whatever else is on the page. The browser keeps Tab inside it and the page behind it still. Focus goes to
// "Cancel", the answer that changes nothing; Escape closes it, as "Cancel" does; the screen returns focus to the button
// that opened it.
export function FlagDialog({ onConfirm, onCancel }: { onConfirm(): void; onCancel(): void }) {
  const box = useRef<HTMLDialogElement>(null)
  const cancel = useRef<HTMLButtonElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = box.current
    if (dialog === null) return
    if (!dialog.open) dialog.showModal()
    cancel.current?.focus()
    return () => {
      if (dialog.open) dialog.close()
    }
  }, [])

  return (
    <dialog
      ref={box}
      aria-labelledby={titleId}
      onCancel={(event) => {
        // The browser's own Escape: close through the screen, so its state and focus follow.
        event.preventDefault()
        onCancel()
      }}
      onKeyDown={(event) => {
        if (event.key !== 'Escape') return
        event.preventDefault()
        onCancel()
      }}
      className="m-auto w-11/12 max-w-sm rounded-control border-2 border-outline bg-surface p-4 text-ink backdrop:bg-ink/50"
    >
      <h2 id={titleId} className="text-balance text-heading font-bold">
        <T k="flag.title" />
      </h2>
      <p className="mt-2 text-pretty">
        <T k="flag.body" />
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button ref={cancel} type="button" onClick={onCancel} className={BUTTON}>
          <T k="flag.cancel" />
        </button>
        <button type="button" onClick={onConfirm} className={BUTTON}>
          <T k="flag.confirm" />
        </button>
      </div>
      <div className="mt-4">
        <ScreenLine />
      </div>
    </dialog>
  )
}
