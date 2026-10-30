import { afterEach, describe, expect, it, vi } from 'vitest'
import { stubCanvas } from '../test/camera'
import { encodeJpeg, scaledSize } from './jpeg'

afterEach(() => {
  vi.restoreAllMocks()
})

it('scaledSize brings the longest side down to 1600 px', () => {
  expect(scaledSize(2000, 1500)).toEqual({ width: 1600, height: 1200 })
  expect(scaledSize(1500, 2000)).toEqual({ width: 1200, height: 1600 })
})

it('scaledSize leaves a photo of 1600 px or less unscaled', () => {
  expect(scaledSize(1600, 1200)).toEqual({ width: 1600, height: 1200 })
  expect(scaledSize(800, 600)).toEqual({ width: 800, height: 600 })
})

describe('encodeJpeg', () => {
  const source = document.createElement('canvas')

  it('draws the photo at 1600 px on its longest side and returns the JPEG with the pixels it was made from', async () => {
    const { context, canvases } = stubCanvas()

    const { blob, pixels } = await encodeJpeg(source, 2000, 1500)

    expect(blob.type).toBe('image/jpeg')
    expect(canvases[0]).toMatchObject({ width: 1600, height: 1200 })
    expect(context.drawImage).toHaveBeenCalledWith(source, 0, 0, 1600, 1200)
    expect(context.getImageData).toHaveBeenCalledWith(0, 0, 1600, 1200)
    expect(pixels).toMatchObject({ width: 1600, height: 1200 })
  })

  it('keeps a photo of 1600 px or less at its own size', async () => {
    const { canvases } = stubCanvas()
    const { pixels } = await encodeJpeg(source, 1280, 720)
    expect(canvases[0]).toMatchObject({ width: 1280, height: 720 })
    expect(pixels).toMatchObject({ width: 1280, height: 720 })
  })

  it('encodes once at quality 0.85 when the blob is 450 KB or less', async () => {
    const { qualities } = stubCanvas({ blobBytes: [450_000] })
    const { blob } = await encodeJpeg(source, 2000, 1500)
    expect(qualities).toEqual([0.85])
    expect(blob.size).toBe(450_000)
  })

  it('re-encodes at quality 0.75 when the 0.85 blob is over 450 KB, and returns the second blob', async () => {
    const { qualities } = stubCanvas({ blobBytes: [450_001, 380_000] })
    const { blob } = await encodeJpeg(source, 2000, 1500)
    expect(qualities).toEqual([0.85, 0.75])
    expect(blob.size).toBe(380_000)
  })

  it('never encodes a third time', async () => {
    const { qualities } = stubCanvas({ blobBytes: [600_000, 500_000, 400_000] })
    const { blob } = await encodeJpeg(source, 2000, 1500)
    expect(qualities).toEqual([0.85, 0.75])
    expect(blob.size).toBe(500_000)
  })

  it('rejects when the canvas has no 2D context', async () => {
    // jsdom's own getContext returns null, which is what a browser gives for a context it can't make.
    await expect(encodeJpeg(source, 2000, 1500)).rejects.toThrow('Canvas 2D is not available')
  })

  it('rejects when the canvas cannot encode a JPEG', async () => {
    stubCanvas({ blobBytes: [null] })
    await expect(encodeJpeg(source, 2000, 1500)).rejects.toThrow('Could not encode the photo as JPEG')
  })
})
