import { MicIcon, SquareIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { T } from '../i18n'
import { RecordingCancelled, startRecording, type Recording } from './recorder'

// The app's cap (Ask's spec §4.7): a full clip ends 0.1 s inside the server's 15 s.
const MAX_MS = 14_900

const BUTTON =
  'inline-flex min-h-tap items-center gap-2 rounded-control border-2 border-outline px-4 font-bold ' +
  'enabled:active:bg-ink enabled:active:text-surface disabled:cursor-not-allowed disabled:opacity-50'

type State = { phase: 'idle' } | { phase: 'starting' } | { phase: 'recording'; secondsLeft: number }

// Ask by voice: a tap starts recording, a second tap stops it, and it stops itself at 14.9 s, with the seconds left
// shown as it goes. The clip goes to onClip and is held nowhere else. Leaving the screen, or the page going hidden,
// drops the recording with nothing sent (the recorder's signal and onCancel). `gate` is the first question's notice
// (MS5's useGate), so the microphone is asked for only after it.
export function MicButton({
  disabled,
  gate,
  onRecording,
  onClip,
  onProblem,
}: {
  disabled: boolean
  gate(action: () => void): void
  onRecording(recording: boolean): void
  onClip(wav: Uint8Array): void
  onProblem(err: unknown): void
}) {
  const [state, setState] = useState<State>({ phase: 'idle' })
  const recording = useRef<Recording | undefined>(undefined)
  // Aborted when the screen closes: it abandons a start in progress and cancels a recording.
  const screen = useRef(new AbortController())
  // The latest callbacks, so a recording that ends on its own reaches the screen as it is now.
  const latest = useRef({ onRecording, onClip, onProblem })
  latest.current = { onRecording, onClip, onProblem }

  useEffect(() => {
    const controller = new AbortController()
    screen.current = controller
    return () => {
      controller.abort()
      recording.current?.cancel()
      recording.current = undefined
    }
  }, [])
  const mounted = () => !screen.current.signal.aborted

  const finish = async () => {
    const current = recording.current
    recording.current = undefined
    if (current === undefined) return
    setState({ phase: 'idle' })
    latest.current.onRecording(false)
    let wav: Uint8Array
    try {
      wav = await current.stop()
    } catch (err) {
      if (!(err instanceof RecordingCancelled) && mounted()) latest.current.onProblem(err)
      return
    }
    if (mounted()) latest.current.onClip(wav)
  }

  const begin = async () => {
    setState({ phase: 'starting' })
    latest.current.onRecording(true)
    try {
      const started = await startRecording({
        maxMs: MAX_MS,
        signal: screen.current.signal,
        onTick: (msLeft) => {
          if (msLeft <= 0) void finish()
          else if (mounted()) setState({ phase: 'recording', secondsLeft: Math.ceil(msLeft / 1000) })
        },
        // The page went hidden: the recording is gone, and the button goes back to its start.
        onCancel: () => {
          recording.current = undefined
          if (!mounted()) return
          setState({ phase: 'idle' })
          latest.current.onRecording(false)
        },
      })
      recording.current = started
      setState((now) => (now.phase === 'recording' ? now : { phase: 'recording', secondsLeft: Math.ceil(MAX_MS / 1000) }))
    } catch (err) {
      if (!mounted()) return
      setState({ phase: 'idle' })
      latest.current.onRecording(false)
      if (!(err instanceof RecordingCancelled)) latest.current.onProblem(err)
    }
  }

  if (state.phase === 'recording') {
    return (
      <span className="inline-flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => void finish()} className={BUTTON}>
          <SquareIcon aria-hidden="true" />
          <T k="ask.ui.micStop" />
        </button>
        <span role="timer" aria-live="off" className="tabular-nums">
          <T k="ask.ui.micLeft" vars={{ s: state.secondsLeft }} />
        </span>
      </span>
    )
  }
  return (
    <button
      type="button"
      disabled={disabled || state.phase === 'starting'}
      onClick={() => gate(() => void begin())}
      className={BUTTON}
    >
      <MicIcon aria-hidden="true" />
      <T k="ask.ui.mic" />
    </button>
  )
}
