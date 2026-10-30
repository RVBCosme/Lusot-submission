// Fakes for the camera tests: a stream whose tracks can be stopped and ended, a promise a test settles by hand, a
// video element that plays a frame when told to, and a canvas that records what is drawn and encoded. jsdom has
// none of these, and no test needs a real camera.
import { vi } from 'vitest'

export class FakeTrack extends EventTarget {
  readyState: 'live' | 'ended' = 'live'
  stop = vi.fn(() => {
    this.readyState = 'ended'
  })

  // The device went away or the system took the camera: the track ends by itself and says so.
  end(): void {
    this.readyState = 'ended'
    this.dispatchEvent(new Event('ended'))
  }
}

export function fakeStream(): { stream: MediaStream; track: FakeTrack } {
  const track = new FakeTrack()
  const stream = { getTracks: () => [track], getVideoTracks: () => [track] } as unknown as MediaStream
  return { stream, track }
}

export function deferred<T>(): { promise: Promise<T>; resolve(value: T): void; reject(reason: unknown): void } {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

// Makes the video report a decoded frame of this size, as a browser does once the first frame plays.
export function showFrame(video: HTMLVideoElement, width = 1920, height = 1080): void {
  Object.defineProperty(video, 'readyState', { configurable: true, value: 4 })
  Object.defineProperty(video, 'videoWidth', { configurable: true, value: width })
  Object.defineProperty(video, 'videoHeight', { configurable: true, value: height })
  video.dispatchEvent(new Event('loadeddata'))
}

// A canvas with a recording 2D context. `blobBytes` is the size of each JPEG that toBlob hands back, in order, the
// last one repeating; `null` is a canvas that can't encode. `qualities` lists the quality each toBlob asked for.
// With `hold`, toBlob waits until the test calls `finish()`, so a test can act while a photo is being encoded.
export function stubCanvas({ blobBytes = [1000], hold = false }: { blobBytes?: (number | null)[]; hold?: boolean } = {}) {
  const sizes = [...blobBytes]
  const qualities: unknown[] = []
  const waiting: (() => void)[] = []
  const canvases: HTMLCanvasElement[] = []
  const context = {
    drawImage: vi.fn(),
    getImageData: vi.fn((_x: number, _y: number, width: number, height: number) => new ImageData(width, height)),
  }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(function (this: HTMLCanvasElement) {
    canvases.push(this)
    return context as unknown as CanvasRenderingContext2D
  } as never)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((callback, type, quality) => {
    qualities.push(quality)
    const bytes = sizes.length > 1 ? sizes.shift() : sizes[0]
    const done = () =>
      callback(bytes === null || bytes === undefined ? null : new Blob([new Uint8Array(bytes)], { type: type ?? 'image/png' }))
    if (hold) waiting.push(done)
    else done()
  })
  const finish = () => waiting.splice(0).forEach((done) => done())
  return { context, qualities, canvases, finish }
}
