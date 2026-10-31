import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MicDenied, MicUnavailable, RecordingCancelled, type RecorderDeps, startRecording } from './recorder'

const RATE = 48000
const FRAME = 128 // an AudioWorklet render quantum

type Fakes = ReturnType<typeof fakes>

// A microphone with two tracks, an AudioContext at `rate`, and the worklet node whose port the test posts frames on.
function fakes(rate = RATE) {
  const tracks = [{ stop: vi.fn() }, { stop: vi.fn() }]
  const stream = { getTracks: () => tracks } as unknown as MediaStream
  const source = { connect: vi.fn(), disconnect: vi.fn() }
  const port: { onmessage: ((event: MessageEvent<Float32Array>) => void) | null; close: () => void } = {
    onmessage: null,
    close: vi.fn(),
  }
  const node = { port, connect: vi.fn(), disconnect: vi.fn() }
  const context = {
    sampleRate: rate,
    state: 'suspended',
    destination: {},
    audioWorklet: { addModule: vi.fn(async (_url: string) => {}) },
    createMediaStreamSource: vi.fn(() => source),
    resume: vi.fn<() => Promise<void>>(async () => {}),
    close: vi.fn(async () => {}),
  }
  const deps: RecorderDeps = {
    getUserMedia: vi.fn(async () => stream),
    createContext: vi.fn(() => context as unknown as AudioContext),
    createNode: vi.fn(() => node as unknown as AudioWorkletNode),
    workletUrl: '/assets/recorder.worklet.js',
  }
  // Posts `seconds` of a 440 Hz tone, in render quanta, as the worklet would.
  const speak = (seconds: number) => {
    const frames = Math.ceil((seconds * rate) / FRAME)
    for (let f = 0; f < frames; f++) {
      const frame = new Float32Array(FRAME)
      for (let i = 0; i < FRAME; i++) frame[i] = 0.3 * Math.sin((2 * Math.PI * 440 * (f * FRAME + i)) / rate)
      port.onmessage?.({ data: frame } as MessageEvent<Float32Array>)
    }
  }
  return { tracks, source, node, context, deps, speak }
}

const dataBytes = (wav: Uint8Array) => new DataView(wav.buffer, wav.byteOffset, wav.byteLength).getUint32(40, true)
const released = (f: Fakes) => {
  for (const track of f.tracks) expect(track.stop).toHaveBeenCalledOnce()
  expect(f.context.close).toHaveBeenCalledOnce()
  expect(f.source.disconnect).toHaveBeenCalled()
}

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, 'visibilityState', { value: state, configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}

beforeEach(() => {
  setVisibility('visible')
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('startRecording', () => {
  it('takes the microphone mono, with echo cancellation and noise suppression, and gives a 16 kHz WAV', async () => {
    const f = fakes()
    const ticks: number[] = []

    const recording = await startRecording({ maxMs: 14900, onTick: (ms) => ticks.push(ms) }, f.deps)
    f.speak(2)
    const wav = await recording.stop()

    expect(f.deps.getUserMedia).toHaveBeenCalledWith({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
    expect(f.context.audioWorklet.addModule).toHaveBeenCalledWith('/assets/recorder.worklet.js')
    expect(f.context.resume).toHaveBeenCalled()
    expect(f.source.connect).toHaveBeenCalledWith(f.node)
    expect(f.node.connect).toHaveBeenCalledWith(f.context.destination)
    // 2 s of 48 kHz frames, rounded up to a whole quantum, as 16 kHz 16-bit samples.
    expect(dataBytes(wav)).toBe(Math.floor((Math.ceil((2 * RATE) / FRAME) * FRAME) / 3) * 2)
    expect(wav.length).toBe(44 + dataBytes(wav))
    released(f)
    expect(ticks[0]).toBe(14900)
  })

  it('counts down once a second of audio', async () => {
    const f = fakes()
    const seconds: number[] = []
    const recording = await startRecording({ maxMs: 14900, onTick: (ms) => seconds.push(Math.ceil(ms / 1000)) }, f.deps)

    f.speak(3.5)
    recording.cancel()

    expect(seconds).toEqual([15, 14, 13, 12])
  })

  it('recording stops itself at 14.9 s', async () => {
    const f = fakes()
    const ticks: number[] = []
    const recording = await startRecording({ maxMs: 14900, onTick: (ms) => ticks.push(ms) }, f.deps)

    f.speak(15.5)

    released(f)
    expect(ticks.at(-1)).toBe(0)
    const wav = await recording.stop()
    // Exactly 14.9 s at 16 kHz: a full-length clip never crosses the server's 15 s by an audio quantum.
    expect(dataBytes(wav)).toBe(14.9 * 16000 * 2)
  })

  it('stops itself at 14.9 s at 44.1 kHz too', async () => {
    const f = fakes(44100)
    const recording = await startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)

    f.speak(15.5)

    released(f)
    expect(dataBytes(await recording.stop())).toBe(238_400 * 2)
  })

  it('stops itself at its limit even when no audio arrives', async () => {
    vi.useFakeTimers()
    const f = fakes()
    const recording = await startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)

    await vi.advanceTimersByTimeAsync(14899)
    expect(f.tracks[0].stop).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1001)

    released(f)
    expect(dataBytes(await recording.stop())).toBe(0)
  })

  it('hiding the page cancels the recording', async () => {
    const f = fakes()
    const onCancel = vi.fn()
    const recording = await startRecording({ maxMs: 14900, onTick: () => {}, onCancel }, f.deps)
    f.speak(1)

    setVisibility('hidden')

    released(f)
    expect(onCancel).toHaveBeenCalledOnce()
    await expect(recording.stop()).rejects.toBeInstanceOf(RecordingCancelled)
  })

  it('a page hidden while the worklet loads records nothing', async () => {
    const f = fakes()
    f.context.audioWorklet.addModule.mockImplementation(async () => setVisibility('hidden'))

    await expect(startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)).rejects.toBeInstanceOf(RecordingCancelled)
    released(f)
  })

  it("the caller's signal cancels the recording, and abandons a start in progress", async () => {
    const f = fakes()
    const controller = new AbortController()
    const onCancel = vi.fn()
    const recording = await startRecording({ maxMs: 14900, onTick: () => {}, onCancel, signal: controller.signal }, f.deps)
    f.speak(1)

    controller.abort()

    released(f)
    expect(onCancel).toHaveBeenCalledOnce()
    await expect(recording.stop()).rejects.toBeInstanceOf(RecordingCancelled)

    // Aborted while the microphone is asked for: the microphone that arrives is closed again.
    const late = fakes()
    let grant: (stream: MediaStream) => void = () => {}
    late.deps.getUserMedia = vi.fn(() => new Promise<MediaStream>((resolve) => (grant = resolve)))
    const abandoned = new AbortController()
    const starting = startRecording({ maxMs: 14900, onTick: () => {}, signal: abandoned.signal }, late.deps)
    abandoned.abort()
    grant({ getTracks: () => late.tracks } as unknown as MediaStream)
    await expect(starting).rejects.toBeInstanceOf(RecordingCancelled)
    for (const track of late.tracks) expect(track.stop).toHaveBeenCalledOnce()
    expect(late.context.close).toHaveBeenCalledOnce()

    // Already aborted: nothing is opened.
    const none = fakes()
    await expect(startRecording({ maxMs: 14900, onTick: () => {}, signal: AbortSignal.abort() }, none.deps)).rejects.toBeInstanceOf(
      RecordingCancelled,
    )
    expect(none.deps.createContext).not.toHaveBeenCalled()
    expect(none.deps.getUserMedia).not.toHaveBeenCalled()
  })

  it('makes and resumes its audio context in the tap, before the microphone is waited for', async () => {
    const f = fakes()
    f.deps.getUserMedia = vi.fn(() => new Promise<MediaStream>(() => {}))

    void startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)

    expect(f.deps.createContext).toHaveBeenCalledOnce()
    expect(f.context.resume).toHaveBeenCalledOnce()
  })

  it("resumes a context iOS calls 'interrupted', and leaves a running one alone", async () => {
    const interrupted = fakes()
    interrupted.context.state = 'interrupted'
    await startRecording({ maxMs: 14900, onTick: () => {} }, interrupted.deps)
    expect(interrupted.context.resume).toHaveBeenCalledOnce()

    const running = fakes()
    running.context.state = 'running'
    await startRecording({ maxMs: 14900, onTick: () => {} }, running.deps)
    expect(running.context.resume).not.toHaveBeenCalled()
  })

  it('a context that never starts is MicUnavailable after 3 s, and releases the microphone', async () => {
    vi.useFakeTimers()
    const f = fakes()
    f.context.resume.mockReturnValue(new Promise<void>(() => {}))

    const starting = startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)
    const caught = starting.catch((err: unknown) => err)
    await vi.advanceTimersByTimeAsync(3000)

    expect(await caught).toBeInstanceOf(MicUnavailable)
    for (const track of f.tracks) expect(track.stop).toHaveBeenCalledOnce()
    expect(f.context.close).toHaveBeenCalledOnce()
  })

  it('a first tick that throws releases the microphone', async () => {
    const f = fakes()

    await expect(
      startRecording(
        {
          maxMs: 14900,
          onTick: () => {
            throw new Error('a screen that is gone')
          },
        },
        f.deps,
      ),
    ).rejects.toThrow('a screen that is gone')
    released(f)
  })

  it('cancel releases the microphone once, and stop then rejects', async () => {
    const f = fakes()
    const recording = await startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)

    recording.cancel()
    recording.cancel()
    setVisibility('hidden')

    released(f)
    await expect(recording.stop()).rejects.toBeInstanceOf(RecordingCancelled)
  })

  it('stop twice gives the same clip, and the page hiding after a stop changes nothing', async () => {
    const f = fakes()
    const recording = await startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)
    f.speak(1)

    const first = await recording.stop()
    setVisibility('hidden')

    expect(await recording.stop()).toBe(first)
    released(f)
  })

  it('a refused microphone is MicDenied, and closes the audio context it made', async () => {
    const f = fakes()
    f.deps.getUserMedia = vi.fn(async () => {
      throw new DOMException('Permission denied', 'NotAllowedError')
    })

    await expect(startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)).rejects.toBeInstanceOf(MicDenied)
    expect(f.context.close).toHaveBeenCalledOnce()
  })

  it.each(['NotFoundError', 'SecurityError', 'NotReadableError'])('a microphone that fails with %s is MicUnavailable', async (name) => {
    const f = fakes()
    f.deps.getUserMedia = vi.fn(async () => {
      throw new DOMException('The microphone failed', name)
    })

    await expect(startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)).rejects.toBeInstanceOf(MicUnavailable)
    expect(f.context.close).toHaveBeenCalledOnce()
  })

  it('a worklet that won\'t load is MicUnavailable, and releases the microphone', async () => {
    const f = fakes()
    f.context.audioWorklet.addModule.mockRejectedValue(new DOMException('Unable to load a worklet', 'AbortError'))

    await expect(startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)).rejects.toBeInstanceOf(MicUnavailable)
    for (const track of f.tracks) expect(track.stop).toHaveBeenCalledOnce()
    expect(f.context.close).toHaveBeenCalledOnce()
  })

  // Android's permission dialog can hide the APK's page while the microphone is asked for, so only a page still hidden
  // when the microphone arrives cancels.
  it('a page still hidden when the microphone arrives records nothing, and one shown again records', async () => {
    let grant: (stream: MediaStream) => void = () => {}
    const asking = (f: Fakes) => {
      f.deps.getUserMedia = vi.fn(() => new Promise<MediaStream>((resolve) => (grant = resolve)))
      return startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)
    }
    const hidden = fakes()
    const starting = asking(hidden)
    setVisibility('hidden')
    grant({ getTracks: () => hidden.tracks } as unknown as MediaStream)

    await expect(starting).rejects.toBeInstanceOf(RecordingCancelled)
    for (const track of hidden.tracks) expect(track.stop).toHaveBeenCalledOnce()
    expect(hidden.context.close).toHaveBeenCalledOnce()

    const shown = fakes()
    const again = asking(shown)
    setVisibility('hidden')
    setVisibility('visible')
    grant({ getTracks: () => shown.tracks } as unknown as MediaStream)
    const recording = await again
    shown.speak(1)
    expect(dataBytes(await recording.stop())).toBeGreaterThan(0)
  })

  it('nothing reaches localStorage, IndexedDB or caches', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const open = vi.fn()
    const cacheOpen = vi.fn()
    vi.stubGlobal('indexedDB', { open })
    vi.stubGlobal('caches', { open: cacheOpen })
    const f = fakes()

    const recording = await startRecording({ maxMs: 14900, onTick: () => {} }, f.deps)
    f.speak(2)
    await recording.stop()
    const second = await startRecording({ maxMs: 14900, onTick: () => {} }, fakes().deps)
    second.cancel()

    expect(setItem).not.toHaveBeenCalled()
    expect(open).not.toHaveBeenCalled()
    expect(cacheOpen).not.toHaveBeenCalled()
  })
})
