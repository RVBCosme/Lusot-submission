// Stubs for browser APIs that jsdom lacks, or only reports as "not implemented". Each is a plain, writable
// property, so a test replaces it with vi.spyOn (undone by vi.restoreAllMocks) or vi.stubGlobal.

// jsdom has no canvas. null is what a browser gives for a context it can't make.
HTMLCanvasElement.prototype.getContext = () => null

HTMLMediaElement.prototype.play = () => Promise.resolve()

// No network until a test gives fetch an answer: a screen that reads the API in a test finds no signal at once, as a
// phone with none would, instead of calling a host. A test that wants an answer swaps the API's fetch (vi.mock of
// lib/apiFetch) or spies on this one.
globalThis.fetch = () => Promise.reject(new TypeError('No network in the test environment'))

// No camera until a test gives getUserMedia a stream.
Object.defineProperty(navigator, 'mediaDevices', {
  configurable: true,
  writable: true,
  value: {
    getUserMedia: () => Promise.reject(new DOMException('No camera in the test environment', 'NotFoundError')),
  },
})

// The browser's ImageData: new ImageData(width, height), or new ImageData(data, width, height?) over RGBA bytes.
class ImageDataStub {
  readonly colorSpace = 'srgb'
  readonly data: Uint8ClampedArray
  readonly width: number
  readonly height: number

  constructor(dataOrWidth: Uint8ClampedArray | number, widthOrHeight: number, height?: number) {
    if (typeof dataOrWidth === 'number') {
      this.width = dataOrWidth
      this.height = widthOrHeight
      this.data = new Uint8ClampedArray(4 * dataOrWidth * widthOrHeight)
      return
    }
    const rows = dataOrWidth.length / (4 * widthOrHeight)
    if (!Number.isInteger(rows) || rows === 0 || (height !== undefined && height !== rows)) {
      throw new DOMException('The data does not fit the width and height', 'IndexSizeError')
    }
    this.data = dataOrWidth
    this.width = widthOrHeight
    this.height = rows
  }
}
globalThis.ImageData = ImageDataStub as unknown as typeof ImageData

// Nothing matches (no dark scheme, no reduced motion) until a test says it does.
window.matchMedia = (query: string): MediaQueryList => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => false,
})
