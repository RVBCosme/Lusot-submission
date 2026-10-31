// MS4's layers file as the app draws it (C524, C615): the order its layers go in, and the words each reference carries.
// The words come from the string tables, so they are in the screen's language, and a drop cause the app doesn't know
// reads as a general line and never as a code (amendment 2). Nothing here shows inches.
import { LEVELS, type Level } from '../copy/levels'
import { dropLine, landmarkLine, levelFromLine, type Translate } from '../copy/wording'
import type { Text } from '../i18n'
import type { OverlayData, OverlayRef, Point, Polygon } from '../lib/api'

export type LayerKind = 'water' | 'outline' | 'rim_outline' | 'box' | 'fitted_rim' | 'waterline' | 'label'

type Rim = NonNullable<OverlayRef['rim']>

// One thing to draw. A layer of a reference holds the reference too, and is dimmed when the reference was dropped.
export type OverlayLayer =
  | { kind: 'water'; polygons: Polygon[] }
  | { kind: 'outline' | 'rim_outline'; ref: OverlayRef; dimmed: boolean; polygons: Polygon[] }
  | { kind: 'box'; ref: OverlayRef; dimmed: boolean }
  | { kind: 'fitted_rim'; ref: OverlayRef; dimmed: boolean; rim: Rim }
  | { kind: 'waterline'; ref: OverlayRef; dimmed: boolean; line: [Point, Point] }
  | { kind: 'label'; ref: OverlayRef; dimmed: boolean }

const KIND_KEYS = {
  wheel: 'overlay.ref.wheel',
  body: 'overlay.ref.body',
  person: 'overlay.ref.person',
} as const

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const isPoint = (value: unknown): value is Point => Array.isArray(value) && value.length === 2 && value.every(finite)
const isPolygon = (value: unknown): value is Polygon => Array.isArray(value) && value.length > 0 && value.every(isPoint)
const isBox = (value: unknown): value is OverlayRef['box'] => Array.isArray(value) && value.length === 4 && value.every(finite)
const isKind = (value: unknown): value is OverlayRef['kind'] => typeof value === 'string' && Object.hasOwn(KIND_KEYS, value)
const isLevel = (value: unknown): value is Level => LEVELS.includes(value as Level)

// The polygons a layer holds, or none for a layer the file leaves null, empty or out of shape.
function polygonsOf(value: unknown): Polygon[] {
  return Array.isArray(value) ? value.filter(isPolygon) : []
}

function rimOf(value: unknown): Rim | undefined {
  const rim = value as Partial<Rim> | null | undefined
  return rim != null && isPoint(rim.center) && isPoint(rim.axes) && rim.axes.every((axis) => axis > 0) && finite(rim.angle)
    ? (rim as Rim)
    : undefined
}

// MS4's draw order (C524): the water first, then each reference in `refs` order, with its outline, its rim outline, its
// box, its fitted rim, its waterline and its label. A layer the file holds as null or empty is left out, and so is a
// reference whose box can't be placed or whose kind can't be named, so a file in the wrong shape draws less and never
// throws. A reference with a drop cause is dimmed (§4.2).
export function orderLayers(data: OverlayData): OverlayLayer[] {
  const layers: OverlayLayer[] = []
  const water = polygonsOf(data.water)
  if (water.length > 0) layers.push({ kind: 'water', polygons: water })
  for (const ref of Array.isArray(data.refs) ? data.refs : []) {
    if (!isBox(ref?.box) || !isKind(ref.kind)) continue
    const dimmed = typeof ref.dropped === 'string'
    const outline = polygonsOf(ref.outline)
    if (outline.length > 0) layers.push({ kind: 'outline', ref, dimmed, polygons: outline })
    const rimOutline = polygonsOf(ref.rim_outline)
    if (rimOutline.length > 0) layers.push({ kind: 'rim_outline', ref, dimmed, polygons: rimOutline })
    layers.push({ kind: 'box', ref, dimmed })
    const rim = rimOf(ref.rim)
    if (rim !== undefined) layers.push({ kind: 'fitted_rim', ref, dimmed, rim })
    if (Array.isArray(ref.waterline) && ref.waterline.length === 2 && ref.waterline.every(isPoint)) {
      layers.push({ kind: 'waterline', ref, dimmed, line: ref.waterline })
    }
    layers.push({ kind: 'label', ref, dimmed })
  }
  return layers
}

const capitalise = (words: string) => words.charAt(0).toUpperCase() + words.slice(1)

// "Knee", or "At least tire" for a floor, as the result card's level line is, without its "deep at this spot".
function levelWords(t: Translate, level: Level, isFloor: boolean): Text {
  const name = t(`result.levelName.${level}`)
  return isFloor ? t('overlay.floor', { level: name.text }) : { text: capitalise(name.text), lang: name.lang }
}

// A floor only where the reference has a level: the flag is true, and false, null or missing is an exact reading.
const floorOf = (ref: OverlayRef) => ref.level_is_floor === true

// The words behind a reference's number: its drop cause alone for a dropped one, with no level; otherwise the level, the
// landmark where the water meets it, and that the rim's size set the level when it did.
function reading(t: Translate, ref: OverlayRef): Text[] {
  if (typeof ref.dropped === 'string') return [dropLine(t, ref.dropped)]
  if (!isLevel(ref.level)) {
    const landmark = typeof ref.landmark === 'string' ? landmarkLine(t, ref.landmark) : undefined
    return landmark === undefined ? [] : [landmark]
  }
  const level = levelWords(t, ref.level, floorOf(ref))
  const parts: Text[] = [{ text: `${level.text}.`, lang: level.lang }]
  const landmark = typeof ref.landmark === 'string' ? landmarkLine(t, ref.landmark) : undefined
  if (landmark !== undefined) parts.push(landmark)
  const from = levelFromLine(t, ref.level_from ?? undefined)
  if (from !== undefined) parts.push(from)
  return parts
}

// The label a screen reader gets for one reference: "Wheel 3: Knee. Water reaches ... Measured from the size of the wheel
// rim." or, for a dropped one, "Wheel 2: Not used, since the vehicle may be moving." Rebuilt from the layers file's
// `kind`, `landmark`, `level`, `level_from` and `level_is_floor` (C615). It adds to the card's own text and replaces none.
export function refLabel(t: Translate, ref: OverlayRef): Text {
  const head = t(KIND_KEYS[ref.kind], { id: ref.id })
  const parts = reading(t, ref)
  return parts.length === 0 ? head : { text: `${head.text}: ${parts.map((part) => part.text).join(' ')}`, lang: head.lang }
}

// The short words written on the photo beside a box: its number, then the level, "At least" the level for a floor, or
// "Not used" for a dropped reference. The full label is `refLabel`.
export function refChip(t: Translate, ref: OverlayRef): Text {
  const said =
    typeof ref.dropped === 'string'
      ? t('overlay.notUsed')
      : isLevel(ref.level)
        ? levelWords(t, ref.level, floorOf(ref))
        : undefined
  return said === undefined ? { text: String(ref.id), lang: t('overlay.notUsed').lang } : { text: `${ref.id}: ${said.text}`, lang: said.lang }
}
