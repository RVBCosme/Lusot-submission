import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Line, useT, type Text } from '../i18n'
import { getLayers, type OverlayData, type OverlayRef } from '../lib/api'
import { orderLayers, refChip, refLabel, revealStep, type LayerKind, type OverlayLayer } from '../overlay/layers'

export type OverlayViewProps = {
  photoUrl: string
  // The overlay JPEG, drawn over the photo when the layers file can't be used (C615).
  overlayUrl?: string
  // MS4's layers file (its C524): the evidence as vectors, drawn here as one still SVG.
  layersUrl?: string
  // Asked once, when the photo link fails to load, so the screen can fetch a new link. A second failure shows no photo.
  // With nothing to ask, the first failure shows none.
  onExpired?(): void
  // What the layers file held once it was read, or undefined when it couldn't be, so the card's caption follows it.
  onLayers?(layers: OverlayData | undefined): void
  // The photo failed again after a new link, and is no longer shown.
  onGone?(): void
}

// Each mark on the photo. Only the palette's tokens colour them, and each is told apart by more than colour: the water
// is dashed, a rim outline is dotted, the box is a rectangle, the fitted rim an ellipse, the waterline has an end tick.
// The class names are written in full because Tailwind finds a class by reading this file. A halo in the surface colour
// is drawn under every mark, so it shows on a bright photo and on a dark one (the JPEG does the same).
type Mark = Exclude<LayerKind, 'label'>
const MARKS: Record<Mark, { stroke: string; dash?: string; cap?: 'round' }> = {
  water: { stroke: 'stroke-action', dash: '10 6' },
  outline: { stroke: 'stroke-depth-6' },
  rim_outline: { stroke: 'stroke-depth-6', dash: '1 6', cap: 'round' },
  box: { stroke: 'stroke-ink' },
  fitted_rim: { stroke: 'stroke-action' },
  waterline: { stroke: 'stroke-action' },
}
const HALO_STROKE = 'stroke-surface'
// A dropped reference: the secondary-text token, at reduced opacity. Its label stays readable (the JPEG's 0.4 and 0.7).
const DIMMED_STROKE = 'stroke-ink-2'
const DIM_MARKS = 0.4
const DIM_LABEL = 0.7
// Widths are in screen pixels whatever the photo's size (`non-scaling-stroke`); only the words scale with the photo.
const LINE_WIDTH = 2
const HALO_WIDTH = 5

type Stroke = {
  className: string
  strokeWidth: number
  strokeDasharray?: string
  vectorEffect: 'non-scaling-stroke'
}

// A mark drawn twice, its halo and then its colour, so `children` is called with each pass's stroke.
function Marked({
  kind,
  dimmed,
  children,
}: {
  kind: Mark
  dimmed: boolean
  children: (stroke: Stroke) => ReactNode
}) {
  const mark = MARKS[kind]
  const pass = (className: string, strokeWidth: number): Stroke => ({
    className,
    strokeWidth,
    strokeDasharray: mark.dash,
    vectorEffect: 'non-scaling-stroke',
  })
  return (
    <g
      data-layer={kind}
      opacity={dimmed ? DIM_MARKS : undefined}
      fill="none"
      strokeLinejoin="round"
      strokeLinecap={mark.cap}
    >
      {children(pass(HALO_STROKE, HALO_WIDTH))}
      {children(pass(dimmed ? DIMMED_STROKE : mark.stroke, LINE_WIDTH))}
    </g>
  )
}

const tenth = (value: number) => Math.round(value * 10) / 10
const points = (polygon: readonly (readonly [number, number])[]) => polygon.map(([x, y]) => `${x},${y}`).join(' ')

// One layer. The words scale with the drawing's width, which is what sets the scale on screen (the photo fills its box's
// width), and the ticks with its short side.
function Layer({ layer, size, chip }: { layer: OverlayLayer; size: { width: number; height: number }; chip: Text | undefined }) {
  const short = Math.min(size.width, size.height)
  switch (layer.kind) {
    case 'water':
    case 'outline':
    case 'rim_outline':
      return (
        <Marked kind={layer.kind} dimmed={layer.kind !== 'water' && layer.dimmed}>
          {(stroke) => layer.polygons.map((polygon, index) => <polygon key={index} points={points(polygon)} {...stroke} />)}
        </Marked>
      )
    case 'box': {
      const [x0, y0, x1, y1] = layer.ref.box
      return (
        <Marked kind="box" dimmed={layer.dimmed}>
          {(stroke) => (
            <rect x={x0} y={y0} width={Math.max(0, x1 - x0)} height={Math.max(0, y1 - y0)} {...stroke} />
          )}
        </Marked>
      )
    }
    case 'fitted_rim': {
      // cv2's axes are full lengths, so the radii are half of them, and the angle turns it about its centre.
      const { center, axes, angle } = layer.rim
      return (
        <Marked kind="fitted_rim" dimmed={layer.dimmed}>
          {(stroke) => (
            <ellipse
              cx={center[0]}
              cy={center[1]}
              rx={axes[0] / 2}
              ry={axes[1] / 2}
              transform={`rotate(${angle} ${center[0]} ${center[1]})`}
              {...stroke}
            />
          )}
        </Marked>
      )
    }
    case 'waterline': {
      const [[x0, y0], [x1, y1]] = layer.line
      const tick = short / 80
      return (
        <Marked kind="waterline" dimmed={layer.dimmed}>
          {(stroke) => (
            <>
              <line x1={x0} y1={y0} x2={x1} y2={y1} {...stroke} />
              <line x1={x0} y1={y0 - tick} x2={x0} y2={y0 + tick} {...stroke} />
              <line x1={x1} y1={y1 - tick} x2={x1} y2={y1 + tick} {...stroke} />
            </>
          )}
        </Marked>
      )
    }
    case 'label': {
      if (chip === undefined) return null
      // The size is the drawing's width over 21, so a photo of any shape shows its words at about 13 px on a card at 360 px
      // (12 px or more), where the short side would make a wide photo's words small (I3). On the box's top edge, or just
      // inside it when there is no room above; the left edge follows the box and stays on the photo, using the width the
      // words will take, since an SVG can't measure them before it is drawn. A label wider than the photo is squeezed to it.
      const font = size.width / 21
      const [x0, y0] = layer.ref.box
      const wide = chip.text.length * font * 0.6
      const room = size.width - font / 2
      const squeezed = wide > room
      const x = Math.min(Math.max(x0, font / 4), Math.max(font / 4, size.width - wide - font / 4))
      const y = Math.min(y0 >= font * 1.4 ? y0 - font * 0.3 : y0 + font * 1.1, size.height - font * 0.3)
      return (
        <g data-layer="label" opacity={layer.dimmed ? DIM_LABEL : undefined}>
          <text
            x={tenth(x)}
            y={tenth(y)}
            fontSize={tenth(font)}
            fontWeight={700}
            paintOrder="stroke"
            strokeWidth={tenth(font / 4)}
            strokeLinejoin="round"
            textLength={squeezed ? tenth(room) : undefined}
            lengthAdjust={squeezed ? 'spacingAndGlyphs' : undefined}
            className="fill-ink stroke-surface"
          >
            {chip.text}
          </text>
        </g>
      )
    }
  }
}

// The layers grouped by what they belong to: the water alone, then each reference with all its marks.
function byReference(layers: OverlayLayer[]): { ref: OverlayRef | null; layers: OverlayLayer[] }[] {
  const groups: { ref: OverlayRef | null; layers: OverlayLayer[] }[] = []
  for (const layer of layers) {
    const ref = layer.kind === 'water' ? null : layer.ref
    const last = groups.at(-1)
    if (last !== undefined && last.ref === ref) last.layers.push(layer)
    else groups.push({ ref, layers: [layer] })
  }
  return groups
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

// How many of the drawing's layers show now. It draws itself (C615): the first layer at once, then layer i at
// i x step, the last by 2,000 ms. With reduced motion, the final frame shows at once. A new layers link unmounts the
// drawing until its file is read, so the next one starts again from its first layer.
function useReveal(count: number): number {
  const [reduced] = useState(prefersReducedMotion)
  const [shown, setShown] = useState(1)
  useEffect(() => {
    if (reduced) return
    const step = revealStep(count)
    const timers: ReturnType<typeof setTimeout>[] = []
    for (let i = 1; i < count; i += 1) timers.push(setTimeout(() => setShown(i + 1), Math.round(i * step)))
    return () => {
      for (const timer of timers) clearTimeout(timer)
    }
  }, [count, reduced])
  return reduced ? count : shown
}

// MS4's layers drawn as an SVG over the photo, scaled with it (C615): the water, then each reference's outline, rim
// outline, box, fitted rim, waterline and label, in MS4's order, one after another. The legend under the photo carries
// each reference's words from the start, so the SVG is hidden from screen readers and nothing is said twice.
function OverlaySvg({ data, layers }: { data: OverlayData; layers: OverlayLayer[] }) {
  const t = useT()
  const size = { width: data.width, height: data.height }
  const shown = useReveal(layers.length)
  const visible = new Set(layers.slice(0, shown))
  return (
    <svg
      data-testid="overlay-svg"
      viewBox={`0 0 ${data.width} ${data.height}`}
      aria-hidden="true"
      focusable="false"
      className="pointer-events-none absolute inset-0 size-full"
    >
      {byReference(layers).map(({ ref, layers: own }, index) => {
        if (ref === null) {
          return (
            <g key={`water-${index}`}>
              {own.map((layer) =>
                visible.has(layer) ? <Layer key={layer.kind} layer={layer} size={size} chip={undefined} /> : null,
              )}
            </g>
          )
        }
        const chip = refChip(t, ref)
        return (
          <g key={`ref-${index}`} data-ref={ref.id} data-dimmed={String(typeof ref.dropped === 'string')}>
            {own.map((layer) =>
              visible.has(layer) ? <Layer key={layer.kind} layer={layer} size={size} chip={chip} /> : null,
            )}
          </g>
        )
      })}
    </svg>
  )
}

// Under the photo: every reference that was drawn, one numbered line each, as `refLabel` gives it. The number is the one
// on its chip, a dropped reference shows its cause, and a used one its level, landmark and how it was measured (C615).
// It is the words for screen readers too, in a list that has the overlay's short label.
function Legend({ layers }: { layers: OverlayLayer[] }) {
  const t = useT()
  const title = t('overlay.title')
  const refs = byReference(layers).flatMap(({ ref }) => (ref === null ? [] : [ref]))
  if (refs.length === 0) return null
  return (
    <ol aria-label={title.text} lang={title.lang} className="mt-2 space-y-1 text-small text-ink-2">
      {refs.map((ref, index) => (
        <li key={index} data-ref={ref.id} data-dimmed={String(typeof ref.dropped === 'string')}>
          <Line value={refLabel(t, ref)} />
        </li>
      ))}
    </ol>
  )
}

// The blurred photo with Lusot's evidence over it. While the layers file is read the photo shows alone. Then the layers
// are drawn as an SVG; if the file can't be used (an expired link, a bucket without GET in its CORS rule, a file in
// another shape), the overlay JPEG goes over the photo instead, and failing that the photo stays alone.
export function OverlayView({ photoUrl, overlayUrl, layersUrl, onExpired, onLayers, onGone }: OverlayViewProps) {
  const t = useT()
  const alt = t('sample.photoAlt')
  const [loaded, setLoaded] = useState<{ url: string; data: OverlayData | undefined }>()
  // The link of the overlay JPEG that failed to load: a new link is tried again. And the one that has loaded, which
  // fades in only then.
  const [failedJpeg, setFailedJpeg] = useState<string>()
  const [loadedJpeg, setLoadedJpeg] = useState<string>()
  const [gone, setGone] = useState(false)
  const failures = useRef(0)
  const told = useRef(onLayers)
  useEffect(() => {
    told.current = onLayers
  }, [onLayers])

  useEffect(() => {
    if (layersUrl === undefined) return
    let live = true
    void getLayers(layersUrl).then((data) => {
      if (!live) return
      setLoaded({ url: layersUrl, data })
      told.current?.(data)
    })
    return () => {
      live = false
    }
  }, [layersUrl])

  // The answer to this link only: a late answer from a link that has been replaced never gets here.
  const settled = layersUrl === undefined || loaded?.url === layersUrl
  const data = layersUrl !== undefined && loaded?.url === layersUrl ? loaded.data : undefined
  const usable = data !== undefined && data.width > 0 && data.height > 0 ? data : undefined
  const layers = useMemo(() => (usable === undefined ? [] : orderLayers(usable)), [usable])
  // The file's drawing, once it is read and holds something to draw.
  const drawn = settled && layers.length > 0 ? usable : undefined

  if (gone) return null

  // The first failure asks for a new link, and the second, or the first with nobody to ask, shows no photo.
  function photoFailed() {
    failures.current += 1
    if (failures.current === 1 && onExpired !== undefined) {
      onExpired()
      return
    }
    setGone(true)
    onGone?.()
  }

  return (
    <div>
      <div className="relative overflow-hidden rounded-control border border-outline">
        <img src={photoUrl} alt={alt.text} lang={alt.lang} onError={photoFailed} className="block w-full" />
        {drawn !== undefined && <OverlaySvg data={drawn} layers={layers} />}
        {/* The JPEG fades in over the photo once it has loaded (C615); reduced motion cuts every transition to its end
            (index.css). */}
        {settled && usable === undefined && overlayUrl !== undefined && failedJpeg !== overlayUrl && (
          <img
            src={overlayUrl}
            alt=""
            aria-hidden="true"
            onLoad={() => setLoadedJpeg(overlayUrl)}
            onError={() => setFailedJpeg(overlayUrl)}
            className={`pointer-events-none absolute inset-0 size-full transition-opacity duration-700 ${loadedJpeg === overlayUrl ? 'opacity-100' : 'opacity-0'}`}
          />
        )}
      </div>
      {drawn !== undefined && <Legend layers={layers} />}
    </div>
  )
}
