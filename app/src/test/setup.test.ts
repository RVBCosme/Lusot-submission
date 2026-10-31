import { afterEach, expect, it, vi } from 'vitest'

// The stubs in setup.ts stand in for browser APIs that jsdom lacks. A test replaces one with vi.spyOn,
// and vi.restoreAllMocks puts the stub back. jsdom's own getContext also gives null, but it writes
// "Not implemented" to the process's stderr, which no spy here can see; the stub keeps that line out.
afterEach(() => {
  vi.restoreAllMocks()
})

it('canvas getContext gives null, until a test gives it a context', () => {
  const canvas = document.createElement('canvas')
  expect(canvas.getContext('2d')).toBeNull()

  const context = {} as CanvasRenderingContext2D
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context)
  expect(canvas.getContext('2d')).toBe(context)
})

it('fetch finds no network, until a test gives it an answer', async () => {
  await expect(fetch('https://api.example.test/map/pins')).rejects.toBeInstanceOf(TypeError)

  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}'))
  await expect(fetch('https://api.example.test/map/pins')).resolves.toBeInstanceOf(Response)
})

it('media play gives a promise that resolves', async () => {
  await expect(document.createElement('video').play()).resolves.toBeUndefined()
})

it('getUserMedia finds no camera, until a test gives it a stream', async () => {
  await expect(navigator.mediaDevices.getUserMedia({ video: true })).rejects.toMatchObject({ name: 'NotFoundError' })

  const stream = {} as MediaStream
  vi.spyOn(navigator.mediaDevices, 'getUserMedia').mockResolvedValue(stream)
  await expect(navigator.mediaDevices.getUserMedia({ video: true })).resolves.toBe(stream)
})

it('matchMedia matches nothing, until a test says it does', () => {
  expect(window.matchMedia('(prefers-reduced-motion: reduce)')).toMatchObject({
    matches: false,
    media: '(prefers-reduced-motion: reduce)',
  })

  vi.spyOn(window, 'matchMedia').mockReturnValue({ matches: true } as MediaQueryList)
  expect(window.matchMedia('(prefers-color-scheme: dark)').matches).toBe(true)
})
