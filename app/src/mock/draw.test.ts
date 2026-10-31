// The mock's images are drawn on a canvas at run time. jsdom has no canvas, so these tests give it a recording
// context; what the drawing looks like is checked in a real browser (the task's report says how).
import { afterEach, expect, it, vi } from 'vitest'
import { drawOverlay, drawPhoto } from './draw'
import { levelLayers } from './fixtures'

afterEach(() => {
  vi.restoreAllMocks()
})

// A 2D context that records the name of each method called on it, and takes any property to be set.
function recordingContext() {
  const calls: string[] = []
  const context = new Proxy(
    {},
    {
      get: (_target, name) => (..._args: unknown[]) => {
        calls.push(String(name))
      },
      set: () => true,
    },
  )
  return { calls, context }
}

function stubCanvas() {
  const { calls, context } = recordingContext()
  const sizes: [number, number][] = []
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as never)
  vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockImplementation(function (this: HTMLCanvasElement) {
    sizes.push([this.width, this.height])
    return 'data:image/jpeg;base64,RHJhd24='
  })
  return { calls, sizes }
}

it('gives a small placeholder image where there is no canvas to draw on', () => {
  const layers = levelLayers('knee')
  expect(drawPhoto(layers, 200)).toMatch(/^data:image\/[a-z]+;base64,/)
  expect(drawOverlay(layers, 200)).toMatch(/^data:image\/[a-z]+;base64,/)
})

it('draws the photo on a canvas the size of the layers, and gives its JPEG', () => {
  const { calls, sizes } = stubCanvas()
  const layers = levelLayers('knee')
  expect(drawPhoto(layers, 200)).toBe('data:image/jpeg;base64,RHJhd24=')
  expect(sizes).toEqual([[layers.width, layers.height]])
  expect(calls).toContain('fillRect')
  expect(calls).toContain('fill')
  // A photo has no outlines or boxes drawn on it.
  expect(calls).not.toContain('stroke')
})

it('draws the overlay over the same photo, with an outline for the water and each reference', () => {
  const photo = stubCanvas()
  drawPhoto(levelLayers('knee'), 200)
  vi.restoreAllMocks()
  const overlay = stubCanvas()
  const layers = levelLayers('knee')
  expect(drawOverlay(layers, 200)).toBe('data:image/jpeg;base64,RHJhd24=')
  expect(overlay.sizes).toEqual([[layers.width, layers.height]])
  expect(overlay.calls.length).toBeGreaterThan(photo.calls.length)
  // At least an outline and a box for each of the 3 references.
  expect(overlay.calls.filter((call) => call === 'stroke').length).toBeGreaterThanOrEqual(layers.refs.length * 2)
})

it('draws a dry street, with no water and no references, without failing', () => {
  const { calls } = stubCanvas()
  expect(drawPhoto({ version: 1, width: 800, height: 600, water: [], refs: [] }, 120)).toMatch(/^data:image\//)
  expect(calls).toContain('fillRect')
})
