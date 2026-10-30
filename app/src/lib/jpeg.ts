// The photo's size and its JPEG (C635): the longest side at most 1,600 px, quality 0.85 first, and 0.75 when that
// result is over 450 KB, so a photo on a weak signal stays near 300 KB.

export const MAX_SIDE_PX = 1600
const FIRST_QUALITY = 0.85
const SECOND_QUALITY = 0.75
const SECOND_PASS_OVER_BYTES = 450_000

// The size with the longest side at most 1600 px and the same proportions. A smaller photo keeps its size.
export function scaledSize(width: number, height: number): { width: number; height: number } {
  const scale = Math.min(1, MAX_SIDE_PX / Math.max(width, height))
  return { width: Math.round(width * scale), height: Math.round(height * scale) }
}

function encode(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('Could not encode the photo as JPEG'))),
      'image/jpeg',
      quality,
    ),
  )
}

// Draws the photo at scaledSize and encodes it as a JPEG. The pixels returned are the ones the JPEG was made from,
// the scaled image, for the phone's quality check (C604). The caller keeps the source, and closes it if it is a bitmap.
export async function encodeJpeg(
  source: CanvasImageSource,
  width: number,
  height: number,
): Promise<{ blob: Blob; pixels: ImageData }> {
  const size = scaledSize(width, height)
  const canvas = document.createElement('canvas')
  canvas.width = size.width
  canvas.height = size.height
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (context === null) throw new Error('Canvas 2D is not available')
  context.drawImage(source, 0, 0, size.width, size.height)
  const pixels = context.getImageData(0, 0, size.width, size.height)
  let blob = await encode(canvas, FIRST_QUALITY)
  if (blob.size > SECOND_PASS_OVER_BYTES) blob = await encode(canvas, SECOND_QUALITY)
  return { blob, pixels }
}
