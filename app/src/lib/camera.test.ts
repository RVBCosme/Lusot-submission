import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { deferred, fakeStream, showFrame, stubCanvas } from '../test/camera'
import { cameraProblem, CameraError, inAppBrowser, openCamera, stopCamera, takeStill } from './camera'

const getUserMedia = vi.fn<(constraints: MediaStreamConstraints) => Promise<MediaStream>>()

beforeEach(() => {
  getUserMedia.mockReset()
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, writable: true, value: { getUserMedia } })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const video = () => document.createElement('video')
const settle = () => vi.advanceTimersByTimeAsync(0)

describe('openCamera', () => {
  it('asks for the rear camera at about 1,920 x 1,080, with no audio', async () => {
    const { stream } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    const element = video()
    showFrame(element)

    await openCamera(element, new AbortController().signal)

    expect(getUserMedia).toHaveBeenCalledExactlyOnceWith({
      audio: false,
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
    })
  })

  it('shows the stream in the video and returns it once a frame plays', async () => {
    vi.useFakeTimers()
    const { stream, track } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    const element = video()
    const opened = openCamera(element, new AbortController().signal)
    const done = vi.fn()
    void opened.then(done)

    await settle()
    expect(element.srcObject).toBe(stream)
    expect(done).not.toHaveBeenCalled()

    showFrame(element)
    await expect(opened).resolves.toBe(stream)
    expect(track.stop).not.toHaveBeenCalled()
    // The first-frame timer is gone once the frame has come.
    expect(vi.getTimerCount()).toBe(0)
  })

  it('no timer while the camera prompt is open: a getUserMedia that stays pending for 30 s raises nothing', async () => {
    vi.useFakeTimers()
    const prompt = deferred<MediaStream>()
    getUserMedia.mockReturnValue(prompt.promise)
    const element = video()
    const opened = openCamera(element, new AbortController().signal)
    const settled = vi.fn()
    opened.then(settled, settled)

    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(settled).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)

    // The person answers at last: the stream opens, and only then does the frame wait begin, with its full 10 s.
    const { stream } = fakeStream()
    prompt.resolve(stream)
    await settle()
    expect(vi.getTimerCount()).toBe(1)
    await vi.advanceTimersByTimeAsync(9_999)
    expect(settled).not.toHaveBeenCalled()
    showFrame(element)
    await expect(opened).resolves.toBe(stream)
  })

  it('rejects with timeout when no frame plays within 10,000 ms of the stream opening, and stops the stream', async () => {
    vi.useFakeTimers()
    const { stream, track } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    const element = video()
    const opened = openCamera(element, new AbortController().signal)
    const failure = vi.fn()
    opened.catch(failure)

    await vi.advanceTimersByTimeAsync(9_999)
    expect(failure).not.toHaveBeenCalled()
    expect(track.stop).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(failure).toHaveBeenCalledOnce()
    const error: unknown = failure.mock.calls[0]?.[0]
    expect(error).toBeInstanceOf(CameraError)
    expect(cameraProblem(error)).toBe('timeout')
    expect(track.stop).toHaveBeenCalledOnce()
    expect(element.srcObject).toBeNull()
  })

  it('a frame at 9,999 ms is in time', async () => {
    vi.useFakeTimers()
    const { stream, track } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    const element = video()
    const opened = openCamera(element, new AbortController().signal)

    await vi.advanceTimersByTimeAsync(9_999)
    showFrame(element)

    await expect(opened).resolves.toBe(stream)
    await vi.advanceTimersByTimeAsync(5_000)
    expect(track.stop).not.toHaveBeenCalled()
  })

  it('a frame with no size yet is not a frame', async () => {
    vi.useFakeTimers()
    const { stream } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    const element = video()
    const opened = openCamera(element, new AbortController().signal)
    const failure = vi.fn()
    opened.catch(failure)

    await settle()
    showFrame(element, 0, 0)
    await vi.advanceTimersByTimeAsync(10_000)

    expect(cameraProblem(failure.mock.calls[0]?.[0])).toBe('timeout')
  })

  it('a late stream is stopped: one that resolves after the signal aborted has every track stopped and is never returned', async () => {
    const prompt = deferred<MediaStream>()
    getUserMedia.mockReturnValue(prompt.promise)
    const controller = new AbortController()
    const opened = openCamera(video(), controller.signal)
    const failure = vi.fn()
    opened.catch(failure)

    controller.abort()
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(failure).toHaveBeenCalledOnce()

    const { stream, track } = fakeStream()
    prompt.resolve(stream)
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(track.stop).toHaveBeenCalledOnce()
    expect(failure).toHaveBeenCalledOnce()
  })

  it('a stream that opens and is then aborted while it waits for its first frame is stopped', async () => {
    vi.useFakeTimers()
    const { stream, track } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    const controller = new AbortController()
    const element = video()
    const opened = openCamera(element, controller.signal)
    const failure = vi.fn()
    opened.catch(failure)

    await settle()
    controller.abort()
    await settle()

    expect(failure).toHaveBeenCalledOnce()
    expect(track.stop).toHaveBeenCalledOnce()
    expect(element.srcObject).toBeNull()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('a stream that is granted and aborted in the same instant is stopped, and is never returned', async () => {
    const { stream, track } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    const controller = new AbortController()
    const element = video()
    const opened = openCamera(element, controller.signal)
    const failure = vi.fn()
    opened.catch(failure)

    // The request has already resolved when the signal aborts, so the abort loses the race to the stream.
    controller.abort()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(failure).toHaveBeenCalledOnce()
    expect(track.stop).toHaveBeenCalledOnce()
    // jsdom leaves srcObject undefined until something sets it; either way, the stream was never shown.
    expect(element.srcObject ?? null).toBeNull()
  })

  it('a frame and an abort in the same instant stop the stream and return nothing', async () => {
    vi.useFakeTimers()
    const { stream, track } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    const controller = new AbortController()
    const element = video()
    const opened = openCamera(element, controller.signal)
    const failure = vi.fn()
    opened.catch(failure)
    await settle()

    showFrame(element)
    controller.abort()
    await settle()

    expect(failure).toHaveBeenCalledOnce()
    expect(track.stop).toHaveBeenCalledOnce()
    expect(element.srcObject).toBeNull()
  })

  it('never asks for the camera when the signal is already aborted', async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(openCamera(video(), controller.signal)).rejects.toBeDefined()
    expect(getUserMedia).not.toHaveBeenCalled()
  })

  it('passes a refusal on as a problem the caller can name', async () => {
    getUserMedia.mockRejectedValue(new DOMException('Permission denied', 'NotAllowedError'))
    const error = await openCamera(video(), new AbortController().signal).catch((err: unknown) => err)
    expect(cameraProblem(error)).toBe('denied')
  })

  it('rejects as unsupported where the browser has no camera API, without asking', async () => {
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, writable: true, value: undefined })
    const error = await openCamera(video(), new AbortController().signal).catch((err: unknown) => err)
    expect(cameraProblem(error)).toBe('unsupported')
  })
})

describe('cameraProblem', () => {
  it.each([
    ['NotAllowedError', 'denied'],
    ['PermissionDeniedError', 'denied'],
    ['NotFoundError', 'no_camera'],
    ['DevicesNotFoundError', 'no_camera'],
    ['NotReadableError', 'no_camera'],
    ['AbortError', 'no_camera'],
    ['OverconstrainedError', 'no_camera'],
    ['SecurityError', 'unsupported'],
    ['TypeError', 'unsupported'],
  ] as const)('reads %s as %s', (name, problem) => {
    expect(cameraProblem(new DOMException('x', name))).toBe(problem)
  })

  it('reads an error object that only carries a name, and anything unknown as unsupported', () => {
    expect(cameraProblem({ name: 'NotAllowedError' })).toBe('denied')
    expect(cameraProblem(new TypeError('mediaDevices is undefined'))).toBe('unsupported')
    expect(cameraProblem('boom')).toBe('unsupported')
    expect(cameraProblem(undefined)).toBe('unsupported')
  })
})

describe('stopCamera', () => {
  it('stops every track', () => {
    const { stream, track } = fakeStream()
    stopCamera(stream)
    expect(track.stop).toHaveBeenCalledOnce()
  })
})

describe('inAppBrowser', () => {
  it.each([
    ['Messenger on iPhone', 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [FBAN/MessengerForiOS;FBAV/460.0.0.45.108;FBBV/563432010;FBDV/iPhone14,5;FBMD/iPhone;FBSN/iOS;FBSV/17.5.1;FBSS/3;FBID/phone;FBLC/en_US;FBOP/5]'],
    ['Messenger on Android', 'Mozilla/5.0 (Linux; Android 13; SM-A546E Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.134 Mobile Safari/537.36 [FB_IAB/MESSENGER;FBAV/470.0.0.31.109;]'],
    ['Facebook on Android', 'Mozilla/5.0 (Linux; Android 12; vivo 2026 Build/SP1A.210812.003; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/125.0.6422.165 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/466.0.0.46.78;]'],
    ['Facebook on iPhone', 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/465.0.0.40.108;FBBV/553246132;FBDV/iPhone13,2;FBMD/iPhone;FBSN/iOS;FBSV/17.5.1;FBSS/3;FBID/phone;FBLC/en_US;FBOP/5;FBRV/0]'],
  ])('knows %s', (_name, userAgent) => {
    expect(inAppBrowser(userAgent)).toBe(true)
  })

  it.each([
    ['Chrome on Android', 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36'],
    ['Safari on iPhone', 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'],
    ['Chrome on Windows', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'],
    ["the APK's own WebView", 'Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP2A.240805.005; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.122 Mobile Safari/537.36'],
    ['an empty user agent', ''],
  ])('does not take %s for one', (_name, userAgent) => {
    expect(inAppBrowser(userAgent)).toBe(false)
  })
})

describe('takeStill', () => {
  // A decoded image with a size, and a close() the test can see.
  const bitmap = (width: number, height: number) => ({ width, height, close: vi.fn() })

  function withImageCapture(still: Blob | Error) {
    const takePhoto = vi.fn(() => (still instanceof Error ? Promise.reject(still) : Promise.resolve(still)))
    const constructed = vi.fn()
    class FakeImageCapture {
      constructor(track: unknown) {
        constructed(track)
      }
      takePhoto = takePhoto
    }
    vi.stubGlobal('ImageCapture', FakeImageCapture)
    return { takePhoto, constructed }
  }

  function playingVideo(width: number, height: number): HTMLVideoElement {
    const element = video()
    showFrame(element, width, height)
    return element
  }

  it('takes the still with ImageCapture where the browser has it', async () => {
    const { stream, track } = fakeStream()
    const { takePhoto, constructed } = withImageCapture(new Blob(['jpeg']))
    const still = bitmap(4000, 3000)
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(still))

    const result = await takeStill(stream, playingVideo(1920, 1080))

    expect(constructed).toHaveBeenCalledWith(track)
    expect(takePhoto).toHaveBeenCalledOnce()
    expect(result).toBe(still)
    expect(still.close).not.toHaveBeenCalled()
  })

  it("a still keeps the preview's orientation: a landscape still under a portrait preview is not used, and the video frame is", async () => {
    const { stream } = fakeStream()
    withImageCapture(new Blob(['jpeg']))
    const landscape = bitmap(4000, 3000)
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(landscape))
    const { canvases, context } = stubCanvas()
    const preview = playingVideo(1080, 1920)

    const result = await takeStill(stream, preview)

    expect(landscape.close).toHaveBeenCalledOnce()
    expect(result).toBe(canvases[0])
    expect(result).toMatchObject({ width: 1080, height: 1920 })
    expect(context.drawImage).toHaveBeenCalledWith(preview, 0, 0)
  })

  it('a portrait still under a landscape preview is not used either', async () => {
    const { stream } = fakeStream()
    withImageCapture(new Blob(['jpeg']))
    const portrait = bitmap(3000, 4000)
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(portrait))
    stubCanvas()

    const result = await takeStill(stream, playingVideo(1920, 1080))

    expect(portrait.close).toHaveBeenCalledOnce()
    expect(result).toMatchObject({ width: 1920, height: 1080 })
  })

  it('takes the current video frame where the browser has no ImageCapture', async () => {
    const { stream } = fakeStream()
    const { canvases, context } = stubCanvas()
    const preview = playingVideo(1280, 720)

    const result = await takeStill(stream, preview)

    expect(result).toBe(canvases[0])
    expect(result).toMatchObject({ width: 1280, height: 720 })
    expect(context.drawImage).toHaveBeenCalledWith(preview, 0, 0)
  })

  it('falls back to the video frame when ImageCapture fails', async () => {
    const { stream } = fakeStream()
    withImageCapture(new DOMException('no photo', 'UnknownError'))
    stubCanvas()

    const result = await takeStill(stream, playingVideo(1920, 1080))

    expect(result).toMatchObject({ width: 1920, height: 1080 })
  })

  it('refuses a still from a track that has ended, so a frozen frame never counts as a fresh photo', async () => {
    const { stream, track } = fakeStream()
    stubCanvas()
    track.end()

    const error = await takeStill(stream, playingVideo(1920, 1080)).catch((err: unknown) => err)

    expect(cameraProblem(error)).toBe('no_camera')
  })

  it('refuses a video that has no frame yet', async () => {
    const { stream } = fakeStream()
    stubCanvas()
    await expect(takeStill(stream, video())).rejects.toBeInstanceOf(CameraError)
  })
})
