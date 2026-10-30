import { afterEach, beforeEach, expect, it, vi } from 'vitest'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const STORED = '0f8e4a52-3c1d-4b7a-9e26-5d0c8b1f7a43'

// A fresh module for each test, so the id the module keeps for its session starts empty.
async function loadDevice() {
  vi.resetModules()
  return import('./device')
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

it('getDeviceId returns the same UUID twice, and keeps it in lusot.device', async () => {
  const { getDeviceId } = await loadDevice()

  const id = getDeviceId()

  expect(id).toMatch(UUID)
  expect(getDeviceId()).toBe(id)
  expect(localStorage.getItem('lusot.device')).toBe(id)
})

it('getDeviceId is made with crypto.randomUUID', async () => {
  const randomUUID = vi.spyOn(crypto, 'randomUUID').mockReturnValue(STORED)
  const { getDeviceId } = await loadDevice()

  expect(getDeviceId()).toBe(STORED)
  expect(randomUUID).toHaveBeenCalledOnce()
})

it('getDeviceId keeps the id across launches', async () => {
  localStorage.setItem('lusot.device', STORED)
  const { getDeviceId } = await loadDevice()

  expect(getDeviceId()).toBe(STORED)
})

it('getDeviceId replaces a stored value that is not a UUID', async () => {
  localStorage.setItem('lusot.device', 'not a device id')
  const { getDeviceId } = await loadDevice()

  const id = getDeviceId()

  expect(id).toMatch(UUID)
  expect(localStorage.getItem('lusot.device')).toBe(id)
})

it('getDeviceId keeps one stable id per session when storage throws', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('full', 'QuotaExceededError')
  })
  const { getDeviceId } = await loadDevice()

  const id = getDeviceId()

  expect(id).toMatch(UUID)
  expect(getDeviceId()).toBe(id)
  expect(getDeviceId()).toBe(id)
})

it('getDeviceId logs nothing', async () => {
  const spies = (['log', 'info', 'warn', 'error', 'debug'] as const).map((name) =>
    vi.spyOn(console, name).mockImplementation(() => {}),
  )
  const { getDeviceId } = await loadDevice()

  getDeviceId()

  for (const spy of spies) expect(spy).not.toHaveBeenCalled()
})
