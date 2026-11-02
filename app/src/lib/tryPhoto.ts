// A photo the person chose from their device (C534, C640), made ready to send: upright, at most 1,600 px, a JPEG, and
// with none of the file's own details (EXIF, GPS included), because only the pixels are drawn to the canvas.
import { encodeJpeg } from './jpeg'

// The types the browser can decode everywhere Lusot runs. A HEIC or GIF is refused before any decode.
export const TRY_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const

// Why a chosen file can't be sent: a type Lusot doesn't read, or a file that won't open as the image it says it is.
export class TryPhotoError extends Error {
  readonly kind: 'unsupported' | 'unreadable'

  constructor(kind: 'unsupported' | 'unreadable') {
    super(`The chosen photo is ${kind}`)
    this.name = 'TryPhotoError'
    this.kind = kind
  }
}

// The chosen file as a JPEG blob. `from-image` turns a sideways phone photo upright, as the person sees it. An older
// engine that doesn't know the option throws a TypeError for it, so the decode is tried once more with no options; any
// other failure is a file that won't open.
export async function photoToJpeg(file: Blob): Promise<Blob> {
  if (!(TRY_TYPES as readonly string[]).includes(file.type)) throw new TryPhotoError('unsupported')
  let bitmap: ImageBitmap
  try {
    try {
      bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
    } catch (err) {
      if (!(err instanceof TypeError)) throw err
      bitmap = await createImageBitmap(file)
    }
  } catch {
    throw new TryPhotoError('unreadable')
  }
  try {
    return (await encodeJpeg(bitmap, bitmap.width, bitmap.height)).blob
  } finally {
    bitmap.close()
  }
}
