// The mock's images, drawn on a canvas at run time from the layers they go with, so a photo and its overlay always
// agree and no photo enters the repo. Flat shapes only: a street, a car, a person, the flood. Where there is no canvas
// (the test environment), a one-pixel placeholder stands in.
import type { OverlayData, Polygon } from '../lib/api'

const PLACEHOLDER = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
const JPEG_QUALITY = 0.8
const OUTLINE_COLOURS = { wheel: '#ffd24a', person: '#ff6fb5', body: '#6fd0ff' } as const

function trace(ctx: CanvasRenderingContext2D, polygon: Polygon): void {
  ctx.beginPath()
  polygon.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)))
  ctx.closePath()
}

function paintPhoto(ctx: CanvasRenderingContext2D, layers: OverlayData, hue: number): void {
  const { width, height } = layers
  const horizon = Math.round(height * 0.38)

  ctx.fillStyle = `hsl(${hue} 35% 80%)`
  ctx.fillRect(0, 0, width, horizon)
  // A row of buildings of different heights.
  const block = width / 6
  for (let i = 0; i < 6; i++) {
    const tall = 70 + ((i * 37) % 90)
    ctx.fillStyle = `hsl(${hue} 14% ${50 + (i % 3) * 7}%)`
    ctx.fillRect(i * block + 4, horizon - tall, block - 8, tall)
  }
  ctx.fillStyle = 'hsl(30 8% 42%)'
  ctx.fillRect(0, horizon, width, height - horizon)
  ctx.fillStyle = 'hsl(45 15% 80%)'
  for (let x = 20; x < width; x += 140) ctx.fillRect(x, Math.round(height * 0.62), 70, 8)

  for (const ref of layers.refs) {
    const [x0, y0, x1, y1] = ref.box
    if (ref.kind === 'wheel') {
      // A parked car with this wheel at its front.
      ctx.fillStyle = `hsl(${(hue + 160) % 360} 40% 38%)`
      ctx.fillRect(x0 - 110, y0 - 100, x1 - x0 + 330, (y1 - y0) / 2 + 100)
      ctx.fillRect(x0 + 10, y0 - 165, 190, 65)
      const radius = (x1 - x0) / 2
      ctx.fillStyle = '#17181a'
      ctx.beginPath()
      ctx.arc((x0 + x1) / 2, (y0 + y1) / 2, radius, 0, 2 * Math.PI)
      ctx.fill()
      ctx.fillStyle = '#b8bcc2'
      ctx.beginPath()
      ctx.arc((x0 + x1) / 2, (y0 + y1) / 2, radius * 0.62, 0, 2 * Math.PI)
      ctx.fill()
    } else if (ref.kind === 'person') {
      const head = (x1 - x0) * 0.28
      ctx.fillStyle = '#c9a07e'
      ctx.beginPath()
      ctx.arc((x0 + x1) / 2, y0 + head, head, 0, 2 * Math.PI)
      ctx.fill()
      ctx.fillStyle = `hsl(${(hue + 80) % 360} 45% 40%)`
      ctx.fillRect(x0, y0 + 2 * head, x1 - x0, y1 - y0 - 2 * head)
    } else {
      ctx.fillStyle = `hsl(${(hue + 160) % 360} 40% 38%)`
      ctx.fillRect(x0, y0, x1 - x0, y1 - y0)
    }
  }

  ctx.fillStyle = 'rgba(108, 82, 52, 0.62)'
  for (const polygon of layers.water) {
    trace(ctx, polygon)
    ctx.fill()
  }

  // So nobody takes it for a photo.
  ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
  ctx.font = '14px sans-serif'
  ctx.fillText('Generated test image', 12, 22)
}

function paintOverlay(ctx: CanvasRenderingContext2D, layers: OverlayData): void {
  ctx.lineWidth = 3
  ctx.strokeStyle = '#33e0ff'
  for (const polygon of layers.water) {
    trace(ctx, polygon)
    ctx.stroke()
  }
  for (const ref of layers.refs) {
    const [x0, y0, x1, y1] = ref.box
    // C524: a dropped reference is drawn dimmed.
    ctx.globalAlpha = ref.dropped === null ? 1 : 0.45
    ctx.strokeStyle = OUTLINE_COLOURS[ref.kind]
    for (const polygon of ref.outline) {
      trace(ctx, polygon)
      ctx.stroke()
    }
    for (const polygon of ref.rim_outline ?? []) {
      trace(ctx, polygon)
      ctx.stroke()
    }
    trace(ctx, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    ctx.stroke()
    if (ref.waterline !== null) {
      ctx.strokeStyle = '#ffffff'
      ctx.beginPath()
      ctx.moveTo(...ref.waterline[0])
      ctx.lineTo(...ref.waterline[1])
      ctx.stroke()
    }
    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 20px sans-serif'
    ctx.fillText(String(ref.id), x0 + 4, y0 + 22)
  }
  ctx.globalAlpha = 1
}

function render(layers: OverlayData, draw: (ctx: CanvasRenderingContext2D) => void): string {
  const canvas = document.createElement('canvas')
  canvas.width = layers.width
  canvas.height = layers.height
  const ctx = canvas.getContext('2d')
  if (ctx === null) return PLACEHOLDER
  draw(ctx)
  return canvas.toDataURL('image/jpeg', JPEG_QUALITY)
}

// A street scene with the car, the people and the flood that `layers` describes, as a data: URL.
export function drawPhoto(layers: OverlayData, hue: number): string {
  return render(layers, (ctx) => paintPhoto(ctx, layers, hue))
}

// The same scene with C524's marks drawn on it: the water's outline, then each reference's outline, rim, box,
// waterline and number.
export function drawOverlay(layers: OverlayData, hue: number): string {
  return render(layers, (ctx) => {
    paintPhoto(ctx, layers, hue)
    paintOverlay(ctx, layers)
  })
}
