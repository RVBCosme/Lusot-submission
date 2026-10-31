// The phone's quality check (C604): MS3a's two scores, computed on the 1,600 px image before it is encoded, exactly as
// the server's backend/analysis/src/lusot_analysis/pipeline/quality.py computes them with OpenCV, and its cutoffs
// (held in tuning.py; quality.test.ts reads both files so the two never drift). The check only warns: "Send anyway"
// always sends, and the server checks again for free.

import { scaledSize } from './jpeg'

// The server's cutoffs: brightness under 40.0 is too_dark, sharpness under 25.0 is too_blurry, dark checked first.
export const BRIGHTNESS_MIN = 40
export const SHARPNESS_MIN = 25

export type QualityScores = { brightness: number; sharpness: number }
export type QualityRefusal = 'too_dark' | 'too_blurry'

// OpenCV's border for the Laplacian (BORDER_REFLECT_101): reflect without repeating the edge pixel, gfedcb|abcdefgh|gfedcba.
function reflect101(i: number, n: number): number {
  if (n === 1) return 0
  let at = i
  while (at < 0 || at >= n) at = at < 0 ? -at : 2 * n - 2 - at
  return at
}

// The mean grey value, and the population variance of the 3 x 3 Laplacian (0 1 0 / 1 -4 1 / 0 1 0) over every pixel.
// Grey is OpenCV 4's 8-bit rule for RGB: (R*9798 + G*19235 + B*3735 + 16384) >> 15. (The plan gave the older 14-bit
// rule, which differs by one on some pixels; the golden test caught it.) Alpha is ignored.
export function qualityScores(img: { width: number; height: number; data: ArrayLike<number> }): QualityScores {
  const { width, height, data } = img
  const count = width * height
  if (count === 0) return { brightness: 0, sharpness: 0 }
  const grey = new Uint8Array(count)
  let sum = 0
  for (let p = 0; p < count; p += 1) {
    const at = p * 4
    const value = (data[at]! * 9798 + data[at + 1]! * 19235 + data[at + 2]! * 3735 + 16384) >> 15
    grey[p] = value
    sum += value
  }
  const laplacian = new Float64Array(count)
  let lapSum = 0
  for (let y = 0; y < height; y += 1) {
    const up = reflect101(y - 1, height) * width
    const down = reflect101(y + 1, height) * width
    const row = y * width
    for (let x = 0; x < width; x += 1) {
      const left = reflect101(x - 1, width)
      const right = reflect101(x + 1, width)
      const value = grey[up + x]! + grey[down + x]! + grey[row + left]! + grey[row + right]! - 4 * grey[row + x]!
      laplacian[row + x] = value
      lapSum += value
    }
  }
  const lapMean = lapSum / count
  let squares = 0
  for (let p = 0; p < count; p += 1) squares += (laplacian[p]! - lapMean) ** 2
  return { brightness: sum / count, sharpness: squares / count }
}

// The scores of a still as the phone sends it: drawn at the JPEG's own 1,600 px size and smoothing (jpeg.ts), on a
// canvas of its own, and read back before anything is encoded. Any failure gives undefined, and then no check shows:
// the check must never stop a photo (C604).
export function scoreStill(source: CanvasImageSource, width: number, height: number): QualityScores | undefined {
  try {
    const size = scaledSize(width, height)
    const canvas = document.createElement('canvas')
    canvas.width = size.width
    canvas.height = size.height
    const context = canvas.getContext('2d', { willReadFrequently: true })
    if (context === null || typeof context.getImageData !== 'function') return undefined
    context.imageSmoothingEnabled = true
    context.imageSmoothingQuality = 'high'
    context.drawImage(source, 0, 0, size.width, size.height)
    return qualityScores(context.getImageData(0, 0, size.width, size.height))
  } catch {
    return undefined
  }
}

// The server's refusal for these scores, or null: dark first, so a dark, flat photo reads too_dark.
export function qualityRefusal(scores: QualityScores): QualityRefusal | null {
  if (scores.brightness < BRIGHTNESS_MIN) return 'too_dark'
  if (scores.sharpness < SHARPNESS_MIN) return 'too_blurry'
  return null
}
