import { CameraIcon } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { T, useT } from '../../i18n'
import type { StringKey } from '../../i18n/en'
import { cameraProblem, inAppBrowser, openCamera, stopCamera, takeStill, type CameraProblem } from '../../lib/camera'
import { encodeJpeg, MAX_SIDE_PX } from '../../lib/jpeg'
import { scoreStill, type QualityScores } from '../../lib/quality'

// `quality`: the phone's scores of the still (Task 10), or undefined when they couldn't be read, which shows no check.
export type Photo = { blob: Blob; capturedAt: string; smallStill: boolean; quality?: QualityScores }

// A problem is one of the camera's four, the in-app browser (no attempt is made there), or a shutter that gave no photo.
type Problem = CameraProblem | 'in_app' | 'capture'
type Status = 'starting' | 'open' | 'taking' | Problem

const PROBLEM_LINE: Record<Problem, StringKey> = {
  denied: 'camera.denied',
  no_camera: 'camera.noCamera',
  unsupported: 'camera.unsupported',
  timeout: 'camera.timeout',
  in_app: 'camera.inApp',
  capture: 'camera.capture',
}
const isProblem = (status: Status): status is Problem => status in PROBLEM_LINE

// Pressing a control fills it with ink and turns its text to the page's colour (S5-R6), as on the gates' screen.
const PRESSED = 'enabled:active:border-ink enabled:active:bg-ink enabled:active:text-surface'
const BUTTON = `min-h-tap min-w-tap rounded-control border px-4 font-bold ${PRESSED}`
const LINK = 'inline-flex min-h-tap min-w-tap items-center text-action underline underline-offset-4'

// The report flow's first step (C602): a live view from the rear camera, drawn inside the layout's <main>, so the
// layout's screen-line bar stays above it; it is not a dialog, a popover or fullscreen, which would cover that bar.
// The still comes from the stream and from nowhere else, and the photo stays in memory.
//
// The camera is on only while this view is on screen and the page is in front. It stops when the view unmounts,
// when the app goes to the background, when the system takes it away, and at the shutter, before the photo is
// encoded. A stream that arrives after any of those is stopped by openCamera. Coming back to the front opens it
// again; after the shutter it never opens again. `onStreamOpen` is called once, the first time a frame plays, so the
// parent can start the location fix then (C603), after the camera's prompt and never at the same moment.
export function CameraStep({ onPhoto, onStreamOpen }: { onPhoto(photo: Photo): void; onStreamOpen(): void }) {
  const t = useT()
  const headingId = useId()
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const alive = useRef(false)
  const announced = useRef(false)
  const shuttered = useRef(false)
  const latest = useRef({ onPhoto, onStreamOpen })
  const [inApp] = useState(() => inAppBrowser(navigator.userAgent))
  const [status, setStatus] = useState<Status>(inApp ? 'in_app' : 'starting')
  const [attempt, setAttempt] = useState(0)
  const [hidden, setHidden] = useState(() => document.visibilityState === 'hidden')

  useEffect(() => {
    latest.current = { onPhoto, onStreamOpen }
  })

  // False once the view has closed, so a photo that finishes late goes nowhere.
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  useEffect(() => {
    const sync = () => setHidden(document.visibilityState === 'hidden')
    document.addEventListener('visibilitychange', sync)
    return () => document.removeEventListener('visibilitychange', sync)
  }, [])

  // Turns the camera off and empties the video.
  function turnOff() {
    const stream = streamRef.current
    streamRef.current = null
    if (stream !== null) stopCamera(stream)
    if (videoRef.current !== null) videoRef.current.srcObject = null
  }

  // Opens the camera while the view is on screen with the page in front; its cleanup turns it off, and aborts a
  // request still waiting on the permission prompt.
  useEffect(() => {
    const video = videoRef.current
    if (video === null || inApp || hidden || shuttered.current) return
    const controller = new AbortController()
    setStatus('starting')
    openCamera(video, controller.signal).then(
      (stream) => {
        // A close can land between openCamera resolving and this callback, since React may render in a microtask.
        // The cleanup then found no stream to stop, so this one is stopped here.
        if (controller.signal.aborted) {
          stopCamera(stream)
          return
        }
        streamRef.current = stream
        // The system can take the camera away (another app, the phone's background). Then the view is no longer live.
        const onEnded = () => {
          turnOff()
          setStatus('no_camera')
        }
        for (const track of stream.getVideoTracks()) track.addEventListener('ended', onEnded, { once: true })
        setStatus('open')
        if (!announced.current) {
          announced.current = true
          latest.current.onStreamOpen()
        }
      },
      (err: unknown) => {
        if (!controller.signal.aborted) setStatus(cameraProblem(err))
      },
    )
    return () => {
      controller.abort()
      turnOff()
    }
  }, [attempt, hidden, inApp])

  async function shoot() {
    const stream = streamRef.current
    const video = videoRef.current
    // The ref is the guard against a double tap: the second tap comes before the button has re-rendered disabled.
    if (status !== 'open' || shuttered.current || stream === null || video === null) return
    shuttered.current = true
    const capturedAt = new Date().toISOString()
    setStatus('taking')
    let still: ImageBitmap | HTMLCanvasElement | undefined
    let photo: Photo
    try {
      still = await takeStill(stream, video)
      // The still is in hand: the camera has no more work, so it goes off before the photo is encoded.
      turnOff()
      if (!alive.current) return
      const { width, height } = still
      const { blob } = await encodeJpeg(still, width, height)
      photo = { blob, capturedAt, smallStill: Math.max(width, height) < MAX_SIDE_PX, quality: scoreStill(still, width, height) }
    } catch {
      // Nothing to log: an error here could carry a frame's data or a position (CLAUDE.md). The person tries again.
      turnOff()
      shuttered.current = false
      if (alive.current) setStatus('capture')
      return
    } finally {
      if (still !== undefined && !(still instanceof HTMLCanvasElement)) still.close()
    }
    // A photo that finished after the view closed goes nowhere.
    if (alive.current) latest.current.onPhoto(photo)
  }

  const problem = isProblem(status) ? status : null

  return (
    <section aria-labelledby={headingId} className="flex min-h-full flex-col">
      <h1 id={headingId} className="text-title font-bold">
        <T k="camera.title" />
      </h1>
      {problem !== null && (
        <div role="alert" className="mt-3 max-w-prose">
          <p>
            <T k={PROBLEM_LINE[problem]} />
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1">
            {problem !== 'in_app' && problem !== 'unsupported' && (
              <button
                type="button"
                onClick={() => setAttempt((count) => count + 1)}
                className={`${BUTTON} border-action bg-action text-on-action`}
              >
                <T k="result.tryAgain" />
              </button>
            )}
            <a href="#/tested" className={LINK}>
              <T k="camera.samples" />
            </a>
          </div>
        </div>
      )}
      {/* The video stays mounted while a problem shows, so a try again has its element, and is hidden then. */}
      <div hidden={problem !== null} className="mt-2 flex min-h-0 flex-1 flex-col">
        <p className="max-w-prose text-small text-ink-2">
          <T k="camera.hint" />
        </p>
        <div className="relative mt-3 min-h-40 flex-1 rounded-control border border-outline">
          <video
            ref={videoRef}
            muted
            playsInline
            autoPlay
            aria-label={t('camera.preview').text}
            className="absolute inset-0 size-full rounded-control object-contain"
          />
          {(status === 'starting' || status === 'taking') && (
            <p role="status" className="absolute inset-0 flex items-center justify-center bg-surface p-4 text-center">
              <T k={status === 'starting' ? 'camera.starting' : 'camera.taking'} />
            </p>
          )}
        </div>
        {problem === null && (
          <button
            type="button"
            disabled={status !== 'open'}
            onClick={() => void shoot()}
            className={`${BUTTON} mt-3 flex items-center justify-center gap-2 border-action bg-action text-on-action disabled:cursor-not-allowed disabled:opacity-50`}
          >
            <CameraIcon />
            <T k="camera.shutter" />
          </button>
        )}
      </div>
    </section>
  )
}
