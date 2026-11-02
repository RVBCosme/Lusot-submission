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

  // An engine that doesn't know imageOrientation throws a TypeError for the options object.
  it('decodes again with no options when the first decode throws a TypeError, as an older engine does', async () => {
    const file = photo('image/jpeg')
    const decoded = bitmap(4000, 3000)
    const decode = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("The provided value 'from-image' is not a valid enum value"))
      .mockResolvedValueOnce(decoded)
    vi.stubGlobal('createImageBitmap', decode)
    stubCanvas()

    const jpeg = await photoToJpeg(file)

    expect(jpeg.type).toBe('image/jpeg')
    expect(decode).toHaveBeenCalledTimes(2)
    expect(decode.mock.calls[0][1]).toEqual({ imageOrientation: 'from-image' })
    expect(decode.mock.calls[1]).toEqual([file])
    expect(decoded.close).toHaveBeenCalledOnce()
  })

  it('is unreadable when the decode without options fails too, and after a failure that is not a TypeError it tries only once', async () => {
    const twice = vi.fn().mockRejectedValue(new TypeError('not a valid enum value'))
    vi.stubGlobal('createImageBitmap', twice)
    await expect(photoToJpeg(photo('image/jpeg'))).rejects.toMatchObject({ kind: 'unreadable' })
    expect(twice).toHaveBeenCalledTimes(2)

    const once = vi.fn().mockRejectedValue(new DOMException('bad image', 'InvalidStateError'))
    vi.stubGlobal('createImageBitmap', once)
    await expect(photoToJpeg(photo('image/jpeg'))).rejects.toMatchObject({ kind: 'unreadable' })
    expect(once).toHaveBeenCalledTimes(1)
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
