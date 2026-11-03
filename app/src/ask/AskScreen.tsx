import { LoaderCircleIcon, SendHorizontalIcon } from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { T, useT } from '../i18n'
import type { StringKey } from '../i18n/en'
import { ask, askVoice, HttpError, type AskAnswer, type Here } from '../lib/api'
import { useGate } from '../lib/consent'
import { getDeviceId } from '../lib/device'
import { useHeadingFocus } from '../lib/focus'
import { locationLine, PoorFix, waitForFix } from '../lib/geo'
import { routeHash } from '../router'
import { AnswerView } from './AnswerView'
import { MicButton } from './MicButton'
import { MicDenied, MicUnavailable } from './recorder'

const MAX_CHARS = 300 // the API's limit (Ask's spec §5.1), counted in characters
// "Use my location" waits up to 10 s for a fix of 100 m or better, all told (plan Task 16; the API takes no poorer).
const FIX_WAIT_MS = 10_000
const GOOD_FIX_M = 100
const EXAMPLES: StringKey[] = ['ask.ui.example1', 'ask.ui.example2', 'ask.ui.example3']

const BUTTON =
  'inline-flex min-h-tap items-center gap-2 rounded-control bg-action px-4 font-bold text-on-action ' +
  'enabled:active:bg-ink enabled:active:text-surface disabled:cursor-not-allowed disabled:opacity-50 ' +
  'aria-disabled:cursor-not-allowed aria-disabled:opacity-50'
const CHIP =
  'inline-flex min-h-tap items-center rounded-control border border-outline px-3 text-left ' +
  'enabled:active:bg-ink enabled:active:text-surface disabled:cursor-not-allowed disabled:opacity-50'
const LINK = 'inline-flex min-h-tap min-w-tap items-center text-action underline underline-offset-4'

// What the screen shows under the controls: the last answer, with when it came (its photos' ages count from then), or
// the line for why there is none.
type Shown =
  | { kind: 'answer'; answer: AskAnswer; transcript?: string; at: Date }
  | { kind: 'problem'; key: StringKey; vars?: Record<string, number> }

// Where "Use my location" stands: off, waiting for a fix, holding one, or the line that says why it can't.
type Fixing = { status: 'off' } | { status: 'waiting' } | { status: 'ready' } | { status: 'problem'; key: StringKey }

// Ask Lusot (its spec §4.10, C723): the question box, the mic, "Use my location", three examples, the notice line and
// the answer. The first question of a session passes MS5's notice gate (C605). One request is in flight at a time: the
// box, Ask and the mic wait while one is, and the last answer is cleared as the next question is sent, so an answer
// never shows under a question it isn't for.
export function AskScreen({ apiUrl }: { apiUrl: string }) {
  const t = useT()
  const heading = useRef<HTMLHeadingElement>(null)
  useHeadingFocus(heading, undefined)
  const gate = useGate('notice')
  const boxId = useId()

  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const [shown, setShown] = useState<Shown | undefined>()
  const [locationOn, setLocationOn] = useState(false)
  const [fixing, setFixing] = useState<Fixing>({ status: 'off' })
  const inFlight = useRef(false)
  const live = useRef(new AbortController()) // aborted when the screen closes
  const switchFix = useRef<AbortController | undefined>(undefined) // the fix the switch itself started
  const answerArea = useRef<HTMLDivElement>(null)

  // A new answer or problem is brought into view: on a phone it lands below the examples.
  useEffect(() => {
    if (shown !== undefined) answerArea.current?.scrollIntoView?.({ block: 'start' })
  }, [shown])

  useEffect(() => {
    const controller = new AbortController()
    live.current = controller
    return () => controller.abort()
  }, [])

  // One fix, by waitForFix's rules, cut at 10 s however long it would wait. Undefined when there is none good enough;
  // the line then says why, and no location is sent. A fix that `stop` drops, or the screen's closing, changes nothing.
  const takeFix = useCallback(async (stop?: AbortSignal): Promise<Here | undefined> => {
    const screenGone = live.current.signal
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(new PoorFix()), FIX_WAIT_MS)
    const onStop = () => controller.abort()
    screenGone.addEventListener('abort', onStop, { once: true })
    stop?.addEventListener('abort', onStop, { once: true })
    const dropped = () => screenGone.aborted || stop?.aborted === true
    setFixing({ status: 'waiting' })
    try {
      const fix = await waitForFix({ maxWaitMs: FIX_WAIT_MS, goodM: GOOD_FIX_M, signal: controller.signal })
      if (!dropped()) setFixing({ status: 'ready' })
      return fix
    } catch (err) {
      if (!dropped()) setFixing({ status: 'problem', key: fixLine(err) })
      return undefined
    } finally {
      clearTimeout(timer)
      screenGone.removeEventListener('abort', onStop)
      stop?.removeEventListener('abort', onStop)
    }
  }, [])

  // On, the switch finds a fix at once, so its prompt and its state show before the first question; off drops it.
  const toggleLocation = () => {
    switchFix.current?.abort()
    switchFix.current = undefined
    const on = !locationOn
    setLocationOn(on)
    if (on) {
      switchFix.current = new AbortController()
      void takeFix(switchFix.current.signal)
    } else {
      setFixing({ status: 'off' })
    }
  }

  // Sends one question, once nothing else is in flight. With the location on, a fresh fix comes first, in place of
  // any the switch is still finding; a screen closed meanwhile sends nothing.
  const run = useCallback(
    async (send: (here: Here | undefined) => Promise<Shown>) => {
      if (inFlight.current) return
      inFlight.current = true
      setBusy(true)
      setShown(undefined)
      try {
        let here: Here | undefined
        if (locationOn) {
          switchFix.current?.abort()
          switchFix.current = undefined
          here = await takeFix()
          if (live.current.signal.aborted) return
        }
        const result = await send(here)
        if (!live.current.signal.aborted) setShown(result)
      } finally {
        inFlight.current = false
        if (!live.current.signal.aborted) setBusy(false)
      }
    },
    [locationOn, takeFix],
  )

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const text = question.trim()
    if (text === '' || apiUrl === '' || inFlight.current || recording) return
    gate(() => {
      void run(async (here) => {
        try {
          const { answer } = await ask(apiUrl, { question: text, here }, getDeviceId())
          return { kind: 'answer', answer, at: new Date() }
        } catch (err) {
          return problemOf(err)
        }
      })
    })
  }

  const sendClip = (wav: Uint8Array) => {
    void run(async (here) => {
      try {
        const { answer, transcript } = await askVoice(apiUrl, { audio: wav, here }, getDeviceId())
        return { kind: 'answer', answer, transcript, at: new Date() }
      } catch (err) {
        return problemOf(err)
      }
    })
  }

  const noApi = apiUrl === ''
  const waiting = busy || recording
  return (
    <div className="max-w-prose">
      <h1 ref={heading} className="text-title font-bold outline-none">
        <T k="nav.ask" />
      </h1>
      {noApi && (
        <p className="mt-2">
          <T k="ask.ui.noApi" />
        </p>
      )}

      <form onSubmit={submit} className="mt-4">
        <label htmlFor={boxId} className="block font-bold">
          <T k="ask.ui.questionLabel" />
        </label>
        <div className="mt-1 flex gap-2">
          <input
            id={boxId}
            type="text"
            value={question}
            maxLength={MAX_CHARS}
            readOnly={busy}
            placeholder={t('ask.ui.placeholder').text}
            onChange={(event) => setQuestion(Array.from(event.target.value).slice(0, MAX_CHARS).join(''))}
            className="min-h-tap min-w-0 flex-1 rounded-control border border-outline bg-surface px-3"
          />
          {/* Waiting, it stays focusable (aria-disabled), so the focus a tap put on it isn't lost. */}
          <button type="submit" disabled={noApi} aria-disabled={waiting} className={BUTTON}>
            <SendHorizontalIcon aria-hidden="true" />
            <T k="ask.ui.send" />
          </button>
        </div>
      </form>
      <p className="mt-1 text-small">
        <a href={routeHash({ name: 'privacy' })} className={LINK}>
          <T k="ask.ui.notice" />
        </a>
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <MicButton
          unavailable={noApi}
          waiting={busy}
          gate={gate}
          onRecording={setRecording}
          onClip={sendClip}
          onProblem={(err) => setShown(problemOf(err))}
        />
        <label className="inline-flex min-h-tap items-center gap-2">
          <input
            type="checkbox"
            role="switch"
            checked={locationOn}
            disabled={noApi || busy}
            onChange={toggleLocation}
            className="size-5"
          />
          <T k="ask.ui.location" />
        </label>
      </div>
      {/* Always there, so a screen reader hears why no location was sent. */}
      <p aria-live="polite" className="mt-1 text-small">
        {fixing.status === 'waiting' && <T k="ask.ui.locationWaiting" />}
        {fixing.status === 'problem' && <T k={fixing.key} />}
      </p>

      <div className="mt-4">
        <p className="text-small text-ink-2">
          <T k="ask.ui.examples" />
        </p>
        <div className="mt-1 flex flex-wrap gap-2">
          {EXAMPLES.map((key) => (
            <button key={key} type="button" disabled={busy} onClick={() => setQuestion(t(key).text)} className={CHIP}>
              <T k={key} />
            </button>
          ))}
        </div>
      </div>

      <div ref={answerArea} aria-live="polite" className="scroll-mt-2">
        {busy && (
          <p className="mt-6 inline-flex items-center gap-2">
            <LoaderCircleIcon aria-hidden="true" className="animate-spin motion-reduce:animate-none" />
            <T k="ask.ui.asking" />
          </p>
        )}
        {shown?.kind === 'problem' && (
          <p className="mt-6 font-bold">
            <T k={shown.key} vars={shown.vars} />
          </p>
        )}
        {shown?.kind === 'answer' && (
          <AnswerView answer={shown.answer} transcript={shown.transcript} now={shown.at} onSuggestion={setQuestion} />
        )}
      </div>
    </div>
  )
}

// Why the location couldn't be used, in MS5's lines, but for the two that speak of the report flow: a timeout reads as
// Ask's poor fix, and the refusal to turn location on gets Ask's own line.
function fixLine(err: unknown): StringKey {
  if (err instanceof PoorFix) return 'ask.ui.locationPoor'
  const key = locationLine(err)
  if (key === 'location.poor') return 'ask.ui.locationPoor'
  if (key === 'location.enableDenied') return 'ask.ui.locationTurnOn'
  return key
}

// The line for a question that got no answer (Ask's spec §5.4). A limit names the minutes to the next hour, from the
// API's Retry-After. Nothing here retries: the client already did, for the one case that can be (lib/api.ts).
function problemOf(err: unknown): Shown {
  const problem = (key: StringKey, vars?: Record<string, number>): Shown => ({ kind: 'problem', key, vars })
  if (err instanceof MicDenied) return problem('ask.error.micDenied')
  if (err instanceof MicUnavailable) return problem('ask.error.micUnavailable')
  if (!(err instanceof HttpError)) return problem('ask.error.unavailable')
  const min = Math.max(1, Math.ceil((err.retryAfterMs ?? 3_600_000) / 60_000))
  switch (err.code) {
    case 'question_limit':
      return problem('ask.error.questionLimit', { min })
    case 'question_cap':
      return problem('ask.error.questionCap', { min })
    case 'voice_paused':
      return problem('ask.error.voicePaused')
    case 'bad_audio':
    case 'audio_too_short':
    case 'audio_too_long':
      return problem('ask.error.voiceFailed')
    // A failed or late transcription (voice_failed) lands here too: a passing fault, so it gets the try-again line,
    // not "couldn't hear" (Nov 3).
    default:
      return problem('ask.error.unavailable')
  }
}
