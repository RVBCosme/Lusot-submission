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
