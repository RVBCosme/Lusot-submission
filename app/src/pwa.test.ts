import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { registerServiceWorker, type Register } from './pwa'

let visibility: DocumentVisibilityState = 'visible'

beforeEach(() => {
  vi.useFakeTimers()
  visibility = 'visible'
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility })
})

afterEach(() => {
  vi.useRealTimers()
})

// A fake of vite-plugin-pwa's registerSW in autoUpdate mode: a new deploy's worker takes over by itself and then calls
// onNeedReload, which the app must pass, or the plugin reloads the page itself, busy or not.
function fakeSetup(busy: () => boolean) {
  const check = vi.fn(async () => {})
  const reload = vi.fn()
  let options: Parameters<Register>[0] = {}
  const register: Register = (opts) => {
    options = opts
    opts.onRegisteredSW?.('/sw.js', { update: check } as unknown as ServiceWorkerRegistration)
  }
  const start = () => registerServiceWorker(busy, { native: false, register: async () => register, reload })
  return { start, check, reload, options: () => options, newVersion: () => options.onNeedReload?.() }
}

describe('registerServiceWorker', () => {
  it('registers nothing in the APK', async () => {
    const register = vi.fn()
    await registerServiceWorker(() => false, { native: true, register: async () => register, reload: vi.fn() })
    expect(register).not.toHaveBeenCalled()
  })

  it('passes onNeedReload, so the plugin never reloads the page by itself', async () => {
    const sw = fakeSetup(() => false)
    await sw.start()
    expect(typeof sw.options().onNeedReload).toBe('function')
    expect(sw.options().immediate).toBe(true)
  })

  it('reloads into a new version at once when the report flow holds nothing', async () => {
    const sw = fakeSetup(() => false)
    await sw.start()
    sw.newVersion()
    expect(sw.reload).toHaveBeenCalledTimes(1)
  })

  it('holds the reload while the report flow holds a photo or a report id, and reloads once that ends', async () => {
    let busy = true
    const sw = fakeSetup(() => busy)
    await sw.start()
    sw.newVersion()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(sw.reload).not.toHaveBeenCalled()
    busy = false
    await vi.advanceTimersByTimeAsync(5_000)
    expect(sw.reload).toHaveBeenCalledTimes(1)
    // A second notice while one reload is waiting doesn't reload twice.
    sw.newVersion()
    expect(sw.reload).toHaveBeenCalledTimes(1)
  })

  it('looks for a new deploy when the app comes back to the front, and every hour while it is open', async () => {
    const sw = fakeSetup(() => false)
    await sw.start()
    expect(sw.check).not.toHaveBeenCalled()
    document.dispatchEvent(new Event('visibilitychange'))
    expect(sw.check).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(60 * 60_000)
    expect(sw.check).toHaveBeenCalledTimes(2)
    visibility = 'hidden'
    document.dispatchEvent(new Event('visibilitychange'))
    expect(sw.check).toHaveBeenCalledTimes(2)
  })
})
