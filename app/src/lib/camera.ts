// The in-app camera (C602): the browser's own camera stream, the same on the web and in the APK, whose WebView asks
// Android for CAMERA when a page opens one. It is the only way a photo enters the app: a fresh still from the rear
// camera, never a file or a gallery pick. This module opens and stops the stream and takes the still; the view that
// shows it is screens/report/CameraStep.tsx.

// Once the stream is open, the first frame must come within this long. There is no limit on the permission prompt
// before it, because a person may read it slowly.
export const FIRST_FRAME_TIMEOUT_MS = 10_000

export type CameraProblem = 'denied' | 'no_camera' | 'unsupported' | 'timeout'

// What openCamera and takeStill throw when the cause is the app's own to name, not a browser error.
export class CameraError extends Error {
  readonly problem: CameraProblem

  constructor(problem: CameraProblem) {
    super(problem)
    this.name = 'CameraError'
    this.problem = problem
  }
}

// Which problem a camera error is. The names come from MDN's list for getUserMedia: NotAllowedError is a refusal,
// an insecure page included; NotFoundError, NotReadableError and the rest mean no camera could be used right now;
// anything else (a missing API, a TypeError, SecurityError for a page that may not use media) is a browser that
// can't open one.
export function cameraProblem(err: unknown): CameraProblem {
  if (err instanceof CameraError) return err.problem
  const name = typeof err === 'object' && err !== null && 'name' in err ? err.name : undefined
  switch (name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
      return 'denied'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
    case 'NotReadableError':
    case 'AbortError':
    case 'OverconstrainedError':
      return 'no_camera'
    default:
      return 'unsupported'
  }
}

// Messenger's and Facebook's in-app browsers put FBAN, FBAV or FB_IAB in the user agent. They don't give a page the
// camera reliably, so the app asks the person to open the link in a real browser.
export function inAppBrowser(userAgent: string): boolean {
  return /\b(?:FBAN|FBAV|FB_IAB)\b/.test(userAgent)
}

// Stops every track, which turns the camera off. Stopping a stopped track does nothing.
export function stopCamera(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop()
}

// A promise that rejects with the signal's reason when it aborts, and a way to stop listening.
function whenAborted(signal: AbortSignal): { promise: Promise<never>; release(): void } {
  let release = () => {}
  const promise = new Promise<never>((_, reject) => {
    const onAbort = () => reject(signal.reason)
    signal.addEventListener('abort', onAbort, { once: true })
    release = () => signal.removeEventListener('abort', onAbort)
  })
  return { promise, release }
}

// Resolves when the video has a decoded frame, rejects with `timeout` if none comes in 10 s, or with the signal's
// reason if it aborts first. It starts only once the stream exists, so the permission prompt is never timed.
function firstFrame(video: HTMLVideoElement, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const events = ['loadeddata', 'canplay', 'playing'] as const
    const finish = (settle: () => void) => {
      clearTimeout(timer)
      for (const event of events) video.removeEventListener(event, check)
      signal.removeEventListener('abort', onAbort)
      settle()
    }
    const check = () => {
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0) finish(resolve)
    }
    const onAbort = () => finish(() => reject(signal.reason))
    const timer = setTimeout(() => finish(() => reject(new CameraError('timeout'))), FIRST_FRAME_TIMEOUT_MS)
    for (const event of events) video.addEventListener(event, check)
    signal.addEventListener('abort', onAbort, { once: true })
    // Autoplay starts a muted video anyway. A play() that is refused leaves no frame, and the timer says so.
    video.play().catch(() => {})
    check()
  })
}

// Asks for the rear camera at about 1,920 x 1,080, with no audio, shows it in `video`, and resolves with the stream
// once a frame plays. The stream never outlives a failure: on a timeout or an abort it is stopped before this
// rejects, and a stream that resolves after `signal` aborted is stopped and never returned.
export async function openCamera(video: HTMLVideoElement, signal: AbortSignal): Promise<MediaStream> {
  signal.throwIfAborted()
  const media = navigator.mediaDevices as MediaDevices | undefined
  if (typeof media?.getUserMedia !== 'function') throw new CameraError('unsupported')

  const request = media.getUserMedia({
    audio: false,
    video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
  })
  const aborted = whenAborted(signal)
  let stream: MediaStream
  try {
    stream = await Promise.race([request, aborted.promise])
  } catch (err) {
    // The abort won the race, or the request failed. If a stream still arrives later, a screen that has closed by
    // then must not leave the camera on, so it is stopped on arrival.
    request.then(stopCamera, () => {})
    throw err
  } finally {
    aborted.release()
  }
  if (signal.aborted) {
    stopCamera(stream)
    throw signal.reason
  }

  try {
    video.srcObject = stream
    await firstFrame(video, signal)
    // A frame that comes in the same instant as an abort doesn't keep the stream.
    signal.throwIfAborted()
  } catch (err) {
    stopCamera(stream)
    video.srcObject = null
    throw err
  }
  return stream
}

const isLandscape = ({ width, height }: { width: number; height: number }) => width > height

// A canvas holding the video's current frame at its own size.
function currentFrame(video: HTMLVideoElement): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  const context = canvas.getContext('2d')
  if (context === null) throw new Error('Canvas 2D is not available')
  context.drawImage(video, 0, 0)
  return canvas
}

// The still: ImageCapture's, where the browser has it and its picture keeps the preview's orientation (some
// phones' stills come out turned), and otherwise the video's current frame. A track that has ended gives nothing,
// so a frozen frame is never taken for a fresh photo. The caller closes a returned ImageBitmap.
export async function takeStill(
  stream: MediaStream,
  video: HTMLVideoElement,
): Promise<ImageBitmap | HTMLCanvasElement> {
  const track = stream.getVideoTracks()[0]
  if (track === undefined || track.readyState !== 'live') throw new CameraError('no_camera')
  if (video.videoWidth === 0 || video.videoHeight === 0) throw new CameraError('no_camera')

  if (typeof ImageCapture === 'function') {
    try {
      const still = await createImageBitmap(await new ImageCapture(track).takePhoto())
      if (isLandscape(still) === isLandscape({ width: video.videoWidth, height: video.videoHeight })) return still
      still.close()
    } catch {
      // The browser's own still failed, so the preview's frame, below, is the photo.
    }
  }
  return currentFrame(video)
}
