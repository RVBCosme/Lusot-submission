// A spoken question, recorded in memory (Ask's spec §4.7, C718). Web Audio, not MediaRecorder, whose WebM and MP4
// Meta's transcription refuses: an AudioWorklet hands the page the microphone's frames, and stop() turns them into a
// 16 kHz mono 16-bit WAV. Nothing is written to storage, IndexedDB, the cache or a file. A page that goes hidden
// mid-recording (the app to the background, the screen locked) cancels it, releasing the microphone with nothing kept,
// and so does a caller's signal.
import workletUrl from './recorder.worklet.ts?worker&url'
import { downsample, encodeWav } from './wav'

const PROCESSOR = 'lusot-recorder' // the name recorder.worklet.ts registers
const RATE = 16000
// A recording whose audio stops arriving (a suspended context) still ends this long after its limit.
const BACKSTOP_MS = 1000
// How long a context may take to start before the recorder gives up on it.
const RESUME_MS = 3000

// The microphone was refused, by the person or the browser's settings.
export class MicDenied extends Error {
  constructor() {
    super('The microphone was refused')
    this.name = 'MicDenied'
  }
}

// There is no microphone, or this browser can't record through Web Audio.
export class MicUnavailable extends Error {
  constructor() {
    super('The microphone is unavailable')
    this.name = 'MicUnavailable'
  }
}

// The recording was cancelled, so it has no clip.
export class RecordingCancelled extends Error {
  constructor() {
    super('The recording was cancelled')
    this.name = 'RecordingCancelled'
  }
}

export type Recording = { stop(): Promise<Uint8Array>; cancel(): void }

// What the recorder reaches in the browser, so tests can give it fakes.
export type RecorderDeps = {
  getUserMedia(constraints: MediaStreamConstraints): Promise<MediaStream>
  createContext(): AudioContext
  createNode(context: AudioContext): AudioWorkletNode
  workletUrl: string
}

export function browserRecorder(): RecorderDeps {
  return {
    getUserMedia: (constraints) => {
      if (navigator.mediaDevices?.getUserMedia === undefined) return Promise.reject(new MicUnavailable())
      return navigator.mediaDevices.getUserMedia(constraints)
    },
    createContext: () => new AudioContext(),
    // One channel, explicitly: a stereo microphone is mixed down to mono by the browser, not cut to its left side.
    createNode: (context) => new AudioWorkletNode(context, PROCESSOR, { channelCount: 1, channelCountMode: 'explicit' }),
    workletUrl,
  }
}

export type RecordingOptions = {
  maxMs: number
  onTick(msLeft: number): void
  // The recording cancelled itself: the page went hidden, or `signal` aborted. Nothing was kept.
  onCancel?(): void
  // Aborting it abandons a start still in progress, or cancels the recording (the screen closed).
  signal?: AbortSignal
}

// Starts recording. Call it from the tap itself: the audio context is made and resumed before anything is waited
// for, as iOS Safari allows audio only from a gesture. onTick gets the ms left at the start and each time the whole
// seconds left change, and 0 when the recording stops itself at maxMs (the app gives 14,900, so a full clip never
// crosses the server's 15 s by an audio quantum). stop() gives the clip; after a cancel it rejects.
export async function startRecording(
  { maxMs, onTick, onCancel, signal }: RecordingOptions,
  deps: RecorderDeps = browserRecorder(),
): Promise<Recording> {
  if (signal?.aborted) throw new RecordingCancelled()
  let audio: AudioContext
  try {
    audio = deps.createContext()
  } catch {
    throw new MicUnavailable()
  }
  // iOS reports a context it paused as 'interrupted', so anything not running is resumed.
  const resuming = audio.state === 'running' ? Promise.resolve() : audio.resume()
  resuming.catch(() => {}) // awaited below, unless the microphone fails first
  const closeAudio = () => void audio.close().catch(() => {})

  let stream: MediaStream
  try {
    stream = await deps.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
  } catch (err) {
    closeAudio()
    throw isDenied(err) ? new MicDenied() : new MicUnavailable()
  }
  const stopTracks = () => {
    for (const track of stream.getTracks()) track.stop()
  }
  // Android's permission dialog can hide the page while it asks, so only a page still hidden now cancels.
  if (isHidden() || signal?.aborted) {
    stopTracks()
    closeAudio()
    throw new RecordingCancelled()
  }

  let source: MediaStreamAudioSourceNode
  let node: AudioWorkletNode
  try {
    await audio.audioWorklet.addModule(deps.workletUrl)
    // A context that isn't allowed to start never settles its resume (Web Audio), so the wait has an end.
    await within(resuming, RESUME_MS)
    source = audio.createMediaStreamSource(stream)
    node = deps.createNode(audio)
    source.connect(node)
    node.connect(audio.destination) // the node writes silence; connected, every browser pulls it
  } catch {
    stopTracks()
    closeAudio()
    throw new MicUnavailable()
  }

  const teardown = () => {
    node.port.onmessage = null
    source.disconnect()
    node.disconnect()
    stopTracks()
    closeAudio()
  }
  // Hidden or abandoned while the worklet loaded: no event will come now, so both are checked once more.
  if (isHidden() || signal?.aborted) {
    teardown()
    throw new RecordingCancelled()
  }

  const fromRate = audio.sampleRate
  const limit = Math.round((maxMs * fromRate) / 1000) // in the microphone's samples
  const frames: Float32Array[] = []
  let samples = 0
  let state: 'recording' | 'done' | 'cancelled' = 'recording'
  let clip: Uint8Array | undefined
  let backstop: ReturnType<typeof setTimeout> | undefined

  const release = () => {
    document.removeEventListener('visibilitychange', onVisibility)
    signal?.removeEventListener('abort', onAbort)
    clearTimeout(backstop)
    teardown()
  }
  const finish = (byLimit: boolean) => {
    if (state !== 'recording') return
    state = 'done'
    release()
    if (byLimit) onTick(0)
  }
  const cancel = () => {
    if (state === 'cancelled') return
    if (state === 'recording') release()
    state = 'cancelled'
    frames.length = 0
    clip = undefined
  }
  // A cancel the caller didn't ask for is told to it, so its screen can say the recording is gone.
  const cancelItself = () => {
    if (state !== 'recording') return
    cancel()
    onCancel?.()
  }
  const onVisibility = () => {
    if (isHidden()) cancelItself()
  }
  const onAbort = () => cancelItself()

  let shownSeconds = Math.ceil(maxMs / 1000)
  node.port.onmessage = (event: MessageEvent<Float32Array>) => {
    if (state !== 'recording') return
    const room = limit - samples
    const frame = event.data.length > room ? event.data.subarray(0, room) : event.data
    frames.push(frame)
    samples += frame.length
    if (samples >= limit) {
      finish(true)
      return
    }
    const msLeft = maxMs - (samples * 1000) / fromRate
    if (Math.ceil(msLeft / 1000) !== shownSeconds) {
      shownSeconds = Math.ceil(msLeft / 1000)
      onTick(msLeft)
    }
  }
  document.addEventListener('visibilitychange', onVisibility)
  signal?.addEventListener('abort', onAbort, { once: true })
  backstop = setTimeout(() => finish(true), maxMs + BACKSTOP_MS)
  try {
    onTick(maxMs)
  } catch (err) {
    cancel() // a caller whose first tick throws never gets the recording, so it is released here
    throw err
  }

  return {
    async stop() {
      finish(false)
      if (state === 'cancelled') throw new RecordingCancelled()
      if (clip === undefined) {
        const all = new Float32Array(samples)
        let at = 0
        for (const frame of frames) {
          all.set(frame, at)
          at += frame.length
        }
        frames.length = 0 // the raw audio goes once the clip is made
        clip = encodeWav(downsample(all, fromRate, RATE), RATE)
      }
      return clip
    },
    cancel,
  }
}

// `work`, or a rejection once `ms` pass.
function within(work: Promise<void>, ms: number): Promise<void> {
  let timer: ReturnType<typeof setTimeout> | undefined
  const late = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new MicUnavailable()), ms)
  })
  return Promise.race([work, late]).finally(() => clearTimeout(timer))
}

// Read through a function, so each check reads the page as it is now.
function isHidden(): boolean {
  return document.visibilityState === 'hidden'
}

// A refusal by the person or the browser's settings. A SecurityError is a page that may not ask at all (an insecure
// page, or a permissions policy), which camera.ts also reads as unsupported, not as refused.
function isDenied(err: unknown): boolean {
  const name = (err as { name?: unknown } | null)?.name
  return name === 'NotAllowedError' || name === 'PermissionDeniedError'
}
