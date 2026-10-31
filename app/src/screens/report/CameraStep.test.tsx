import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../../i18n'
import { EN, type StringKey } from '../../i18n/en'
import { FIL } from '../../i18n/fil'
import { Layout } from '../../layout/Layout'
import { writeItem } from '../../lib/storage'
import { deferred, fakeStream, showFrame, stubCanvas } from '../../test/camera'
import cameraStepSource from './CameraStep.tsx?raw'
import { CameraStep } from './CameraStep'

const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
const MESSENGER =
  'Mozilla/5.0 (Linux; Android 13; SM-A546E Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.134 Mobile Safari/537.36 [FB_IAB/MESSENGER;FBAV/470.0.0.31.109;]'

const getUserMedia = vi.fn<(constraints: MediaStreamConstraints) => Promise<MediaStream>>()
const text = (key: StringKey) => EN[key].text
const video = () => document.querySelector('video') as HTMLVideoElement

beforeEach(() => {
  getUserMedia.mockReset()
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, writable: true, value: { getUserMedia } })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('lang')
  Reflect.deleteProperty(document, 'visibilityState')
})

function renderStep() {
  const onPhoto = vi.fn()
  const onStreamOpen = vi.fn()
  const view = render(
    <LanguageProvider>
      <CameraStep onPhoto={onPhoto} onStreamOpen={onStreamOpen} />
    </LanguageProvider>,
  )
  return { onPhoto, onStreamOpen, ...view }
}

// Lets the promises the camera is waiting on, and the renders they cause, run.
const flush = () => act(async () => {})
const shutter = () => screen.getByRole('button', { name: text('camera.shutter') }) as HTMLButtonElement

// A camera that has opened: the stream is granted and the video shows a frame of this size.
async function openWith(width = 1920, height = 1080) {
  const camera = fakeStream()
  getUserMedia.mockResolvedValue(camera.stream)
  const step = renderStep()
  await flush()
  await act(async () => showFrame(video(), width, height))
  return { ...camera, ...step }
}

function hidePage(hidden: boolean) {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => (hidden ? 'hidden' : 'visible') })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('the camera view', () => {
  it('waits for the camera with the shutter off, and tells a slow reader to allow it', async () => {
    getUserMedia.mockReturnValue(deferred<MediaStream>().promise)
    renderStep()
    await flush()

    expect(screen.getByRole('heading', { name: text('camera.title') })).toBeTruthy()
    expect(screen.getByText(text('camera.hint'))).toBeTruthy()
    expect(screen.getByText(text('camera.starting'))).toBeTruthy()
    expect(shutter().disabled).toBe(true)
  })

  it('opens the stream in a muted, inline video, and tells Task 12 once, when the first frame plays', async () => {
    const { onStreamOpen, stream } = await openWith()

    expect(video().srcObject).toBe(stream)
    expect(video().muted).toBe(true)
    expect(video().hasAttribute('playsinline')).toBe(true)
    expect(onStreamOpen).toHaveBeenCalledOnce()
    expect(shutter().disabled).toBe(false)
    expect(screen.queryByText(text('camera.starting'))).toBeNull()
  })

  it('says nothing about opening until a frame has played', async () => {
    getUserMedia.mockResolvedValue(fakeStream().stream)
    const { onStreamOpen } = renderStep()
    await flush()
    expect(onStreamOpen).not.toHaveBeenCalled()
    expect(shutter().disabled).toBe(true)
  })

  it('is not a dialog, a popover or fullscreen, so the layout\'s screen line stays above it', () => {
    const code = cameraStepSource.replace(/\/\/.*$/gm, '')
    expect(code).not.toMatch(/showModal|showPopover|requestFullscreen|<dialog|popover/i)
  })

  it('has the screen line once, in the layout\'s bar and outside the camera view, and nothing else', async () => {
    getUserMedia.mockResolvedValue(fakeStream().stream)
    render(
      <LanguageProvider>
        <Layout route={{ name: 'report' }} apiReady>
          <CameraStep onPhoto={vi.fn()} onStreamOpen={vi.fn()} />
        </Layout>
      </LanguageProvider>,
    )
    await flush()

    expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
    const line = screen.getByText(SCREEN_LINE)
    expect(line.getAttribute('lang')).toBe('en')
    expect(screen.getByRole('main').contains(line)).toBe(false)
    expect(document.querySelector('dialog, [popover]')).toBeNull()
    expect(document.fullscreenElement ?? null).toBeNull()
  })
})

describe('when there is no camera to use', () => {
  const samples = () => screen.getByRole('link', { name: text('camera.samples') })

  it('camera refused offers samples: a NotAllowedError shows the camera line and a link to the Tested page', async () => {
    getUserMedia.mockRejectedValue(new DOMException('Permission denied', 'NotAllowedError'))
    const { onPhoto, onStreamOpen } = renderStep()
    await flush()

    expect(screen.getByText(text('camera.denied'))).toBeTruthy()
    expect(samples().getAttribute('href')).toBe('#/tested')
    expect(screen.queryByRole('button', { name: text('camera.shutter') })).toBeNull()
    expect(onStreamOpen).not.toHaveBeenCalled()
    expect(onPhoto).not.toHaveBeenCalled()
  })

  it('in-app browser asks for a real browser, without asking for the camera', async () => {
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(MESSENGER)
    const { onPhoto, onStreamOpen } = renderStep()
    await flush()

    expect(screen.getByText('Open this page in Chrome or Safari to take a photo.')).toBeTruthy()
    expect(samples().getAttribute('href')).toBe('#/tested')
    expect(getUserMedia).not.toHaveBeenCalled()
    expect(onStreamOpen).not.toHaveBeenCalled()
    expect(onPhoto).not.toHaveBeenCalled()
  })

  it.each([
    ['no camera', new DOMException('No camera', 'NotFoundError'), 'camera.noCamera'],
    ['a camera another app holds', new DOMException('In use', 'NotReadableError'), 'camera.noCamera'],
    ['a browser that is not allowed one', new TypeError('mediaDevices is undefined'), 'camera.unsupported'],
  ] as const)('says what to do for %s, and offers the samples', async (_name, error, key) => {
    getUserMedia.mockRejectedValue(error)
    renderStep()
    await flush()

    expect(screen.getByText(text(key))).toBeTruthy()
    expect(samples().getAttribute('href')).toBe('#/tested')
  })

  it('says what to do where the browser has no camera API', async () => {
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, writable: true, value: undefined })
    renderStep()
    await flush()

    expect(screen.getByText(text('camera.unsupported'))).toBeTruthy()
    expect(samples().getAttribute('href')).toBe('#/tested')
  })

  it('a camera that opens but never plays says so after 10 s, stops it, and offers another try and the samples', async () => {
    vi.useFakeTimers()
    const { stream, track } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    renderStep()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_999)
    })
    expect(screen.queryByText(text('camera.timeout'))).toBeNull()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })

    expect(screen.getByText(text('camera.timeout'))).toBeTruthy()
    expect(track.stop).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: text('result.tryAgain') })).toBeTruthy()
    expect(samples().getAttribute('href')).toBe('#/tested')
  })

  it('"Try again" asks for the camera again, and opens it when it works the second time', async () => {
    getUserMedia.mockRejectedValueOnce(new DOMException('No camera', 'NotFoundError'))
    const { onStreamOpen } = renderStep()
    await flush()
    expect(screen.getByText(text('camera.noCamera'))).toBeTruthy()

    const { stream } = fakeStream()
    getUserMedia.mockResolvedValue(stream)
    fireEvent.click(screen.getByRole('button', { name: text('result.tryAgain') }))
    await flush()
    await act(async () => showFrame(video()))

    expect(getUserMedia).toHaveBeenCalledTimes(2)
    expect(screen.queryByText(text('camera.noCamera'))).toBeNull()
    expect(shutter().disabled).toBe(false)
    expect(onStreamOpen).toHaveBeenCalledOnce()
  })

  it('offers no "Try again" in an in-app browser, where trying again changes nothing', async () => {
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(MESSENGER)
    renderStep()
    await flush()
    expect(screen.queryByRole('button', { name: text('result.tryAgain') })).toBeNull()
  })

  it('shows the Taglish draft of a camera line, since camera lines are not screen-line keys', async () => {
    writeItem('lusot.lang', 'fil')
    getUserMedia.mockRejectedValue(new DOMException('Permission denied', 'NotAllowedError'))
    renderStep()
    await flush()
    expect(screen.getByText(FIL['camera.denied'].text)).toBeTruthy()
  })
})

describe('no timer while the camera prompt is open', () => {
  it('a getUserMedia that stays pending for 30,000 ms raises nothing, and the screen keeps waiting', async () => {
    vi.useFakeTimers()
    getUserMedia.mockReturnValue(deferred<MediaStream>().promise)
    renderStep()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(screen.getByText(text('camera.starting'))).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('the camera never stays on', () => {
  it('a late stream is stopped: one that resolves after the step unmounted has every track stopped', async () => {
    const prompt = deferred<MediaStream>()
    getUserMedia.mockReturnValue(prompt.promise)
    const { unmount, onStreamOpen } = renderStep()
    await flush()

    unmount()
    const { stream, track } = fakeStream()
    prompt.resolve(stream)
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(track.stop).toHaveBeenCalledOnce()
    expect(onStreamOpen).not.toHaveBeenCalled()
  })

  it('stops an open stream when the step unmounts', async () => {
    const { unmount, track } = await openWith()
    expect(track.stop).not.toHaveBeenCalled()
    unmount()
    expect(track.stop).toHaveBeenCalledOnce()
  })

  it('under StrictMode\'s double mount, stops the first request\'s stream and keeps the second\'s', async () => {
    const first = fakeStream()
    const second = fakeStream()
    getUserMedia.mockResolvedValueOnce(first.stream).mockResolvedValueOnce(second.stream)
    const onStreamOpen = vi.fn()
    render(
      <StrictMode>
        <LanguageProvider>
          <CameraStep onPhoto={vi.fn()} onStreamOpen={onStreamOpen} />
        </LanguageProvider>
      </StrictMode>,
    )
    await flush()
    await act(async () => showFrame(video()))

    expect(getUserMedia).toHaveBeenCalledTimes(2)
    expect(first.track.stop).toHaveBeenCalledOnce()
    expect(second.track.stop).not.toHaveBeenCalled()
    expect(video().srcObject).toBe(second.stream)
    expect(onStreamOpen).toHaveBeenCalledOnce()
  })

  it('stops the camera when the app goes to the background, and opens it again when the person comes back', async () => {
    const { track, onStreamOpen } = await openWith()

    await act(async () => hidePage(true))
    expect(track.stop).toHaveBeenCalledOnce()
    expect(video().srcObject).toBeNull()

    const again = fakeStream()
    getUserMedia.mockResolvedValue(again.stream)
    await act(async () => hidePage(false))
    await flush()
    await act(async () => showFrame(video()))

    expect(getUserMedia).toHaveBeenCalledTimes(2)
    expect(video().srcObject).toBe(again.stream)
    expect(again.track.stop).not.toHaveBeenCalled()
    expect(shutter().disabled).toBe(false)
    // Task 12 starts the location fix on this call, so it comes once for the step, not at every return.
    expect(onStreamOpen).toHaveBeenCalledOnce()
  })

  it('does not ask for the camera at all while the page is in the background', async () => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' })
    getUserMedia.mockResolvedValue(fakeStream().stream)
    renderStep()
    await flush()
    expect(getUserMedia).not.toHaveBeenCalled()
  })

  it('a stream that arrives while the page is in the background is stopped', async () => {
    const prompt = deferred<MediaStream>()
    getUserMedia.mockReturnValue(prompt.promise)
    renderStep()
    await flush()
    await act(async () => hidePage(true))

    const { stream, track } = fakeStream()
    prompt.resolve(stream)
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(track.stop).toHaveBeenCalledOnce()
  })

  it('shows a problem, and offers another try, when the system takes the camera away', async () => {
    const { track } = await openWith()

    await act(async () => track.end())

    expect(screen.getByText(text('camera.noCamera'))).toBeTruthy()
    expect(screen.queryByRole('button', { name: text('camera.shutter') })).toBeNull()
    expect(video().srcObject).toBeNull()
    expect(screen.getByRole('button', { name: text('result.tryAgain') })).toBeTruthy()
  })
})

describe('the shutter', () => {
  // A 1,920 x 1,080 frame from the video, the canvas fakes that stand in for encoding, and a clock set by the test.
  async function press({ width = 1920, height = 1080, bytes = [200_000] }: { width?: number; height?: number; bytes?: number[] } = {}) {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-30T09:15:30.000Z'))
    const canvas = stubCanvas({ blobBytes: bytes })
    const step = await openWith(width, height)
    fireEvent.click(shutter())
    await flush()
    return { ...step, ...canvas }
  }

  it('calls onPhoto once with a JPEG and the shutter time, and keeps no pixel array', async () => {
    const { onPhoto } = await press()

    expect(onPhoto).toHaveBeenCalledOnce()
    const photo = onPhoto.mock.calls[0]?.[0]
    expect(photo.blob).toBeInstanceOf(Blob)
    expect(photo.blob.type).toBe('image/jpeg')
    expect(photo.capturedAt).toBe('2026-10-30T09:15:30.000Z')
    expect(photo.smallStill).toBe(false)
    // The quality check's two scores, never the pixels; with no pixels to read (this canvas fake has none), no scores.
    expect(Object.keys(photo).sort()).toEqual(['blob', 'capturedAt', 'quality', 'smallStill'])
    expect(photo.quality).toBeUndefined()
  })

  it('scores the still for the quality check, as two numbers and no pixel array (Task 10)', async () => {
    stubCanvas({ grey: 20 })
    const { onPhoto } = await openWith()
    fireEvent.click(shutter())
    await flush()
    const photo = onPhoto.mock.calls[0]?.[0]
    expect(photo.quality).toEqual({ brightness: 20, sharpness: 0 })
    expect(Object.values(photo).some((value) => value instanceof Uint8ClampedArray)).toBe(false)
  })

  it('stamps the time of the press, not the time the photo finished', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-30T09:15:30.000Z'))
    stubCanvas()
    const { onPhoto } = await openWith()
    fireEvent.click(shutter())
    vi.setSystemTime(new Date('2026-10-30T09:16:00.000Z'))
    await flush()
    expect(onPhoto.mock.calls[0]?.[0].capturedAt).toBe('2026-10-30T09:15:30.000Z')
  })

  it('a double tap makes one photo, whether the two taps share a render or come one after the other', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    stubCanvas()
    const { onPhoto } = await openWith()
    const button = shutter()
    // Both taps run before React has drawn the first one's result, so the button is still enabled for the second.
    act(() => {
      button.click()
      button.click()
    })
    await flush()
    fireEvent.click(button)
    await flush()
    expect(onPhoto).toHaveBeenCalledOnce()
  })

  it('stops the camera at the shutter, and never turns it on again, whatever the page does next', async () => {
    const { track } = await press()
    expect(track.stop).toHaveBeenCalledOnce()
    expect(video().srcObject).toBeNull()

    await act(async () => hidePage(true))
    await act(async () => hidePage(false))
    await flush()

    expect(getUserMedia).toHaveBeenCalledTimes(1)
    expect(track.stop).toHaveBeenCalledOnce()
  })

  it('a 1,280 x 720 still sets smallStill, and a 1,920 x 1,080 one does not', async () => {
    const small = await press({ width: 1280, height: 720 })
    expect(small.onPhoto.mock.calls[0]?.[0].smallStill).toBe(true)
    cleanup()
    vi.restoreAllMocks()
    getUserMedia.mockReset()

    const large = await press({ width: 1920, height: 1080 })
    expect(large.onPhoto.mock.calls[0]?.[0].smallStill).toBe(false)
  })

  it('a still of exactly 1,600 px on its longer side is not small', async () => {
    const { onPhoto } = await press({ width: 1600, height: 1200 })
    expect(onPhoto.mock.calls[0]?.[0].smallStill).toBe(false)
  })

  it('takes the photo only from the stream: no photo when the track has already ended', async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    stubCanvas()
    const { onPhoto, track } = await openWith()
    // The track ends without the page hearing about it yet: the press must still not take a stale frame.
    track.readyState = 'ended'
    fireEvent.click(shutter())
    await flush()

    expect(onPhoto).not.toHaveBeenCalled()
    expect(screen.getByText(text('camera.capture'))).toBeTruthy()
    // A still that fails turns the camera off: the step can't be left with the camera on.
    expect(track.stop).toHaveBeenCalled()
    expect(video().srcObject).toBeNull()
  })

  it('says so, with another try, when the photo cannot be encoded', async () => {
    stubCanvas({ blobBytes: [null] })
    const { onPhoto } = await openWith()
    fireEvent.click(shutter())
    await flush()

    expect(onPhoto).not.toHaveBeenCalled()
    expect(screen.getByText(text('camera.capture'))).toBeTruthy()
    expect(screen.getByRole('button', { name: text('result.tryAgain') })).toBeTruthy()
  })

  it('drops the photo when the step closed before the still was ready', async () => {
    stubCanvas()
    const { onPhoto, unmount, track } = await openWith()
    fireEvent.click(shutter())
    unmount()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(onPhoto).not.toHaveBeenCalled()
    expect(track.stop).toHaveBeenCalled()
  })

  it('drops the photo when the step closed while it was being encoded', async () => {
    const canvas = stubCanvas({ hold: true })
    const { onPhoto, unmount } = await openWith()
    fireEvent.click(shutter())
    await flush()
    unmount()
    canvas.finish()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(onPhoto).not.toHaveBeenCalled()
  })
})
