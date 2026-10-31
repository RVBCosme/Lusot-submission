// The fake camera's picture for the end-to-end suite (MS5 Task 18). Chromium's --use-file-for-fake-video-capture plays a
// Y4M file as the camera, so this writes one: a street-like scene (sky, a row of buildings, a road, a parked car and a
// person, with water over the lower road) drawn from rectangles and circles. Nothing here is a photograph, and no real
// place or person is in it. The file goes to the git-ignored e2e/.frames/ before the browser starts (global-setup.ts).
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export const FRAMES_DIR = fileURLToPath(new URL('./.frames/', import.meta.url))
export const STREET_FRAME = fileURLToPath(new URL('./.frames/street.y4m', import.meta.url))

// 1,600 px on the longer side, so the still isn't "too small" (C602) and the place step shows no warning.
const WIDTH = 1600
const HEIGHT = 1200
const FRAME_COUNT = 2

type Rgb = [number, number, number]

// A small deterministic noise, so the picture has texture and not flat fills.
function noise(x: number, y: number): number {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263)
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  return ((h ^ (h >>> 16)) & 0xff) / 255
}

const inRect = (x: number, y: number, x0: number, y0: number, x1: number, y1: number) =>
  x >= x0 && x < x1 && y >= y0 && y < y1
const inCircle = (x: number, y: number, cx: number, cy: number, r: number) => (x - cx) ** 2 + (y - cy) ** 2 <= r * r

// The colour at one pixel. `phase` moves the water's ripples between frames, so the picture isn't frozen.
function colourAt(x: number, y: number, phase: number): Rgb {
  const u = x / WIDTH
  const v = y / HEIGHT
  const grain = (noise(x, y) - 0.5) * 14

  // The car: body, windows and two wheels, standing in the water.
  const wheelY = 0.78 * HEIGHT
  const wheelR = 0.055 * HEIGHT
  for (const wheelX of [0.6 * WIDTH, 0.82 * WIDTH]) {
    if (inCircle(x, y, wheelX, wheelY, wheelR * 0.5)) return [150, 150, 155]
    if (inCircle(x, y, wheelX, wheelY, wheelR)) return [25, 25, 28]
  }
  if (inRect(x, y, 0.62 * WIDTH, 0.5 * HEIGHT, 0.78 * WIDTH, 0.58 * HEIGHT)) return [70, 80, 95]
  if (inRect(x, y, 0.55 * WIDTH, 0.57 * HEIGHT, 0.87 * WIDTH, 0.77 * HEIGHT)) return [170 + grain, 38 + grain, 36 + grain]

  // A person standing at the left.
  if (inCircle(x, y, 0.22 * WIDTH, 0.5 * HEIGHT, 0.028 * HEIGHT)) return [214, 170, 140]
  if (inRect(x, y, 0.2 * WIDTH, 0.53 * HEIGHT, 0.24 * WIDTH, 0.7 * HEIGHT)) return [40, 90, 150]
  if (inRect(x, y, 0.205 * WIDTH, 0.7 * HEIGHT, 0.235 * WIDTH, 0.84 * HEIGHT)) return [50, 50, 60]

  // Sky.
  if (v < 0.3) return [190 + 45 * v + grain, 208 + 35 * v + grain, 228 + 15 * v + grain]
  // A row of buildings, each block its own colour, with a grid of windows.
  if (v < 0.5) {
    const block = Math.floor(u * 9)
    const walls: Rgb[] = [
      [196, 180, 150],
      [150, 96, 78],
      [160, 164, 170],
      [214, 200, 170],
      [128, 120, 116],
      [186, 150, 120],
      [170, 176, 182],
      [200, 172, 140],
      [142, 110, 96],
    ]
    const wall = walls[block % walls.length]!
    const windowCell = Math.floor(x / 26) + Math.floor(y / 30)
    const isWindow = x % 26 > 8 && x % 26 < 20 && y % 30 > 8 && y % 30 < 22 && windowCell % 2 === 0
    return isWindow ? [60 + grain, 74 + grain, 96 + grain] : [wall[0] + grain, wall[1] + grain, wall[2] + grain]
  }
  // The kerb.
  if (v < 0.52) return [176 + grain, 176 + grain, 172 + grain]
  // Water over the lower road, with ripples, and the dry road above it.
  if (v > 0.66) {
    const ripple = Math.sin((u * 60 + v * 18 + phase) * Math.PI) * 7
    return [92 + ripple + grain, 112 + ripple + grain, 120 + ripple + grain]
  }
  // A lane mark on the road.
  if (inRect(x, y, 0, 0.6 * HEIGHT, WIDTH, 0.612 * HEIGHT) && Math.floor(x / 90) % 2 === 0) return [226, 226, 220]
  return [96 + grain, 96 + grain, 102 + grain]
}

const clamp = (value: number) => (value < 0 ? 0 : value > 255 ? 255 : Math.round(value))

// One frame as I420: the Y plane, then U and V at half size in each direction (BT.601, full range, as C420jpeg says).
function frame(phase: number): Buffer {
  const lumaSize = WIDTH * HEIGHT
  const chromaSize = (WIDTH / 2) * (HEIGHT / 2)
  const out = Buffer.alloc(lumaSize + 2 * chromaSize)
  for (let y = 0; y < HEIGHT; y += 1) {
    for (let x = 0; x < WIDTH; x += 1) {
      const [r, g, b] = colourAt(x, y, phase)
      out[y * WIDTH + x] = clamp(0.299 * r + 0.587 * g + 0.114 * b)
      if (x % 2 === 0 && y % 2 === 0) {
        const at = lumaSize + (y / 2) * (WIDTH / 2) + x / 2
        out[at] = clamp(128 - 0.168736 * r - 0.331264 * g + 0.5 * b)
        out[at + chromaSize] = clamp(128 + 0.5 * r - 0.418688 * g - 0.081312 * b)
      }
    }
  }
  return out
}

// Writes the street frame, the same bytes every time.
export function writeFrames(): void {
  mkdirSync(FRAMES_DIR, { recursive: true })
  const header = Buffer.from(`YUV4MPEG2 W${WIDTH} H${HEIGHT} F30:1 Ip A1:1 C420jpeg XYSCSS=420JPEG\n`, 'latin1')
  const marker = Buffer.from('FRAME\n', 'latin1')
  const parts: Buffer[] = [header]
  for (let i = 0; i < FRAME_COUNT; i += 1) parts.push(marker, frame(i))
  writeFileSync(STREET_FRAME, Buffer.concat(parts))
}
