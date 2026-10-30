import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useT, type Text } from '../i18n'
import { getLayers, type OverlayData, type OverlayRef } from '../lib/api'
import { orderLayers, refChip, refLabel, type LayerKind, type OverlayLayer } from '../overlay/layers'

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

// One layer. The photo's short side sets the size of the words and the ticks, so they scale with the photo.
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
      // On the box's top edge, or just inside it when there is no room above; the left edge follows the box and stays on
      // the photo, using the width the words will take, since an SVG can't measure them before it is drawn.
      const font = short / 18
      const [x0, y0] = layer.ref.box
      const wide = chip.text.length * font * 0.6
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

// MS4's layers drawn as one still SVG over the photo, scaled with it (C615): the water, then each reference's outline,
// rim outline, box, fitted rim, waterline and label, in MS4's order. The SVG has a short label, the water has one, and
// each reference has its own from `refLabel`, so the overlay adds evidence and is never the only place a reading is said.
function OverlaySvg({ data, layers }: { data: OverlayData; layers: OverlayLayer[] }) {
  const t = useT()
  const title = t('overlay.title')
  const water = t('overlay.water')
  const size = { width: data.width, height: data.height }
  return (
    <svg
      data-testid="overlay-svg"
      viewBox={`0 0 ${data.width} ${data.height}`}
      role="group"
      aria-label={title.text}
      lang={title.lang}
      focusable="false"
      className="pointer-events-none absolute inset-0 size-full"
    >
      {byReference(layers).map(({ ref, layers: own }, index) => {
        if (ref === null) {
          return (
            <g key={`water-${index}`} role="img" aria-label={water.text} lang={water.lang}>
              {own.map((layer) => (
                <Layer key={layer.kind} layer={layer} size={size} chip={undefined} />
              ))}
            </g>
          )
        }
        const label = refLabel(t, ref)
        const chip = refChip(t, ref)
        return (
          <g
            key={`ref-${index}`}
            role="img"
            aria-label={label.text}
            lang={label.lang}
            data-ref={ref.id}
            data-dimmed={String(typeof ref.dropped === 'string')}
          >
            {own.map((layer) => (
              <Layer key={layer.kind} layer={layer} size={size} chip={chip} />
            ))}
          </g>
        )
      })}
    </svg>
  )
}

// The blurred photo with Lusot's evidence over it. While the layers file is read the photo shows alone. Then the layers
// are drawn as an SVG; if the file can't be used (an expired link, a bucket without GET in its CORS rule, a file in
// another shape), the overlay JPEG goes over the photo instead, and failing that the photo stays alone.
export function OverlayView({ photoUrl, overlayUrl, layersUrl, onExpired, onLayers, onGone }: OverlayViewProps) {
  const t = useT()
  const alt = t('sample.photoAlt')
  const [loaded, setLoaded] = useState<{ url: string; data: OverlayData | undefined }>()
  const [jpegFailed, setJpegFailed] = useState(false)
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
    <div className="relative overflow-hidden rounded-control border border-outline">
      <img src={photoUrl} alt={alt.text} lang={alt.lang} onError={photoFailed} className="block w-full" />
      {settled && usable !== undefined && layers.length > 0 && <OverlaySvg data={usable} layers={layers} />}
      {settled && usable === undefined && overlayUrl !== undefined && !jpegFailed && (
        <img
          src={overlayUrl}
          alt=""
          aria-hidden="true"
          onError={() => setJpegFailed(true)}
          className="pointer-events-none absolute inset-0 size-full"
        />
      )}
    </div>
  )
}
