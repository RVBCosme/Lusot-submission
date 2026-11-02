import { afterEach, describe, expect, it, vi } from 'vitest'
import { stubCanvas } from '../test/camera'
import { photoToJpeg, TRY_TYPES, TryPhotoError } from './tryPhoto'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const bitmap = (width: number, height: number) => ({ width, height, close: vi.fn() })
const photo = (type: string) => new Blob(['photo bytes'], { type })

describe('photoToJpeg', () => {
  it('allows JPEG, PNG and WebP', () => {
    expect([...TRY_TYPES]).toEqual(['image/jpeg', 'image/png', 'image/webp'])
  })

  it.each(['image/heic', 'image/gif', 'application/pdf', ''])(
    'refuses a %j file as unsupported without decoding it',
    async (type) => {
      const decode = vi.fn()
      vi.stubGlobal('createImageBitmap', decode)

      const attempt = photoToJpeg(photo(type))

      await expect(attempt).rejects.toBeInstanceOf(TryPhotoError)
      await expect(attempt).rejects.toMatchObject({ kind: 'unsupported' })
      expect(decode).not.toHaveBeenCalled()
    },
  )

  it('decodes with imageOrientation from-image, so a sideways photo comes out upright', async () => {
    const file = photo('image/jpeg')
    const decode = vi.fn().mockResolvedValue(bitmap(3000, 4000))
    vi.stubGlobal('createImageBitmap', decode)
    stubCanvas()

    await photoToJpeg(file)

    expect(decode).toHaveBeenCalledOnce()
    expect(decode.mock.calls[0][0]).toBe(file)
    expect(decode.mock.calls[0][1]).toEqual({ imageOrientation: 'from-image' })
  })

  it('a 4000x3000 photo comes out at 1600x1200 as image/jpeg', async () => {
    const decoded = bitmap(4000, 3000)
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(decoded))
    const { canvases, context } = stubCanvas()

    const jpeg = await photoToJpeg(photo('image/png'))

    expect(jpeg.type).toBe('image/jpeg')
    expect(canvases[0]).toMatchObject({ width: 1600, height: 1200 })
    expect(context.drawImage).toHaveBeenCalledWith(decoded, 0, 0, 1600, 1200)
  })

  it('a file that will not decode is unreadable', async () => {
    vi.stubGlobal('createImageBitmap', vi.fn().mockRejectedValue(new DOMException('bad image', 'InvalidStateError')))

    const attempt = photoToJpeg(photo('image/jpeg'))

    await expect(attempt).rejects.toBeInstanceOf(TryPhotoError)
    await expect(attempt).rejects.toMatchObject({ kind: 'unreadable' })
  })

  it('closes the bitmap after encoding, and after a failed encode', async () => {
    const encoded = bitmap(4000, 3000)
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(encoded))
    stubCanvas()
    await photoToJpeg(photo('image/webp'))
    expect(encoded.close).toHaveBeenCalledOnce()

    const failed = bitmap(4000, 3000)
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(failed))
    stubCanvas({ blobBytes: [null] })
    await expect(photoToJpeg(photo('image/webp'))).rejects.toThrow('Could not encode the photo as JPEG')
    expect(failed.close).toHaveBeenCalledOnce()
  })
})
