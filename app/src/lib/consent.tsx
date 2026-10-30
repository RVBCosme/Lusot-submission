// The two gates (C605): the 18+ check before the first sample, upload or question, and the consent notice, with
// the same check, before the first upload or question. Components and helpers stay together as one import, so
// Fast Refresh reloads the page when this file changes.
/* oxlint-disable react/only-export-components */
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import consentText from '../content/consent.en.md?raw'
import { navigate } from '../router'
import { ConsentScreen, type GateKind } from '../screens/ConsentScreen'
import { readItem, writeItem } from './storage'

// Kept on the phone as { adult: true, notice?: <version> } (C607).
const CONSENT_KEY = 'lusot.consent'

// FNV-1a, 32 bits, over the text's UTF-8 bytes, as 8 hex digits.
export function fnv1a32(text: string): string {
  let hash = 0x811c9dc5
  for (const byte of new TextEncoder().encode(text)) {
    hash = Math.imul(hash ^ byte, 0x01000193) >>> 0
  }
  return hash.toString(16).padStart(8, '0')
}

// The notice's version is a hash of its own text, so any change to the notice asks everyone again.
export const NOTICE_VERSION = fnv1a32(consentText)

// What the phone keeps, read strictly: anything but adult === true, storage that throws included, passes nothing,
// so a gate never fails open.
function readConsent(): { adult: boolean; notice: string | null } {
  const none = { adult: false, notice: null }
  const raw = readItem(CONSENT_KEY)
  if (raw === null) return none
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return none
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return none
  const { adult, notice } = value as Record<string, unknown>
  if (adult !== true) return none
  return { adult: true, notice: typeof notice === 'string' ? notice : null }
}

export function isAdultConfirmed(): boolean {
  return readConsent().adult
}

export function hasNotice(): boolean {
  return readConsent().notice === NOTICE_VERSION
}

// A write that storage refuses is dropped, and the gate asks again next time.
function keep(kind: GateKind): void {
  writeItem(CONSENT_KEY, JSON.stringify(kind === 'adult' ? { adult: true } : { adult: true, notice: NOTICE_VERSION }))
}

const passed = (kind: GateKind) => (kind === 'adult' ? isAdultConfirmed() : hasNotice())

type Request = (kind: GateKind, action: () => void) => void

const GateContext = createContext<Request | null>(null)

// Mounted in App inside the layout's <main>, so the open gate sits under the screen-line bar, never over it (no
// <dialog>.showModal(), whose top layer would cover the bar). The screen behind it stays mounted, hidden, so the
// action that opened the gate still has its screen when it runs. Layout keys <main> by route, so leaving the
// screen drops a gate left open, with its action.
export function GateProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<GateKind | null>(null)
  const pending = useRef<(() => void) | null>(null)
  const opener = useRef<HTMLElement | null>(null)

  const request = useCallback<Request>((kind, action) => {
    if (passed(kind)) {
      action()
      return
    }
    // A second tap before the gate shows replaces the first, so the action still runs once.
    pending.current = action
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setOpen(kind)
  }, [])

  // Once the gate closes, focus goes back to the control that opened it, unless the action moved it elsewhere.
  useEffect(() => {
    if (open !== null) return
    const target = opener.current
    opener.current = null
    const lost = document.activeElement === null || document.activeElement === document.body
    if (target?.isConnected && lost) target.focus()
  }, [open])

  // Takes the action first, so a double tap on "Continue" runs it once.
  function close(kind: GateKind, accepted: boolean) {
    const action = pending.current
    pending.current = null
    setOpen(null)
    if (!accepted || action === null) return
    keep(kind)
    action()
  }

  return (
    <GateContext value={request}>
      {/* `hidden` beats `contents` only through Tailwind's base rule [hidden] { display: none !important }: without
          it, display: contents would show the screen behind the gate. */}
      <div hidden={open !== null} className="contents">
        {children}
      </div>
      {open !== null && (
        <ConsentScreen key={open} kind={open} onContinue={() => close(open, true)} onCancel={() => close(open, false)} />
      )}
    </GateContext>
  )
}

// Runs the action at once when its gate is passed; otherwise opens the gate, and runs the action after "Continue".
export function useGate(kind: GateKind): (action: () => void) => void {
  const request = useContext(GateContext)
  if (request === null) throw new Error('useGate needs a <GateProvider> above it')
  return useCallback((action: () => void) => request(kind, action), [request, kind])
}

// The notice in place of its children until it is accepted. It guards a screen itself, so a typed #/report meets
// it as a tap on Report does. With storage blocked, "Continue" opens the screen for this visit only.
export function NoticeGate({ children }: { children: ReactNode }) {
  const [accepted, setAccepted] = useState(hasNotice)
  if (accepted) return children
  return (
    <ConsentScreen
      kind="notice"
      onContinue={() => {
        keep('notice')
        setAccepted(true)
      }}
      onCancel={() => navigate({ name: 'map' })}
    />
  )
}
