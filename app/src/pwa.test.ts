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

// A fake of vite-plugin-pwa's registerSW: it keeps the options, and records what the app asked of it.
function fakeRegister() {
  const update = vi.fn(async () => {})
  const check = vi.fn(async () => {})
  let options: Parameters<Register>[0] = {}
  const register: Register = (opts) => {
    options = opts
    opts.onRegisteredSW?.('/sw.js', { update: check } as unknown as ServiceWorkerRegistration)
    return update
  }
  return { register, update, check, needRefresh: () => options.onNeedRefresh?.() }
}

describe('registerServiceWorker', () => {
  it('registers nothing in the APK', async () => {
    const sw = fakeRegister()
    const spy = vi.fn(sw.register)
    await registerServiceWorker(() => false, { native: true, register: async () => spy })
    expect(spy).not.toHaveBeenCalled()
  })

  it('takes a new version at once when nothing is held: the new worker, then a reload', async () => {
    const sw = fakeRegister()
    await registerServiceWorker(() => false, { native: false, register: async () => sw.register })
    sw.needRefresh()
    expect(sw.update).toHaveBeenCalledWith(true)
  })

  it('holds a new version while the report flow holds a photo or a report id, and takes it once that ends', async () => {
    let busy = true
    const sw = fakeRegister()
    await registerServiceWorker(() => busy, { native: false, register: async () => sw.register })
    sw.needRefresh()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(sw.update).not.toHaveBeenCalled()
    busy = false
    await vi.advanceTimersByTimeAsync(5_000)
    expect(sw.update).toHaveBeenCalledTimes(1)
    expect(sw.update).toHaveBeenCalledWith(true)
  })

  it('looks for a new deploy when the app comes back to the front, and every hour while it is open', async () => {
    const sw = fakeRegister()
    await registerServiceWorker(() => false, { native: false, register: async () => sw.register })
    expect(sw.check).not.toHaveBeenCalled()
    document.dispatchEvent(new Event('visibilitychange'))
    expect(sw.check).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(60 * 60_000)
    expect(sw.check).toHaveBeenCalledTimes(2)
    // Not while the page is hidden.
    visibility = 'hidden'
    document.dispatchEvent(new Event('visibilitychange'))
    expect(sw.check).toHaveBeenCalledTimes(2)
  })
})
