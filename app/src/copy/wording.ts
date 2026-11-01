// Every line a result can show, built from the string tables so a Taglish screen marks an English fallback
// lang="en" (C619). Each function takes the `t` of makeT or useT and returns a Text. The words live in
// i18n/en.ts and fil.ts; this file only picks the line and fills its numbers. Models never output inches: the app
// words what the API sends (CLAUDE.md).
import type { makeT, Text } from '../i18n'
import {
  BODY_FLOORS,
  DROP_CAUSES,
  FAILED_REASONS,
  OFF_GAUGE,
  PASSABILITY,
  PEOPLE_LANDMARKS,
  REFUSED_REASONS,
  WHEEL_LANDMARKS,
  type DropCause,
  type Landmark,
  type Level,
  type Reason,
} from './levels'

export type Translate = ReturnType<typeof makeT>

const LANDMARKS: readonly string[] = [...WHEEL_LANDMARKS, ...PEOPLE_LANDMARKS, ...BODY_FLOORS]
const REASONS: readonly string[] = [...REFUSED_REASONS, ...FAILED_REASONS]
const CAUSES: readonly string[] = DROP_CAUSES

const isLandmark = (word: string): word is Landmark => LANDMARKS.includes(word)
const isReason = (word: string): word is Reason => REASONS.includes(word)
const isDropCause = (word: string): word is DropCause => CAUSES.includes(word)

const capitalise = (words: string) => words.charAt(0).toUpperCase() + words.slice(1)

// "Knee deep at this spot (MMDA level)." The two added levels drop "(MMDA level)", and a floor reads "At least"
// (MS3a's C81, C54).
export function levelLine(t: Translate, level: Level, isFloor: boolean): Text {
  const name = t(`result.levelName.${level}`).text
  const off = OFF_GAUGE.includes(level)
  if (isFloor) return t(off ? 'result.level.offFloor' : 'result.level.floor', { level: name })
  return t(off ? 'result.level.off' : 'result.level.exact', { level: capitalise(name) })
}

// What MMDA lists the level as. The two added levels name the MMDA level they lie beyond instead (C81).
export function classLine(t: Translate, level: Level): Text {
  if (level === 'below_gutter') return t('result.class.belowGutter')
  if (level === 'above_chest') return t('result.class.aboveChest')
  const classes = { PATV: 'result.class.patv', NPLV: 'result.class.nplv', NPATV: 'result.class.npatv' } as const
  return t(classes[PASSABILITY[level]])
}

// Where the water meets the deciding reference. A category that reads no level, or one the app doesn't know, has
// no line, so the card shows none rather than a raw code.
export function landmarkLine(t: Translate, landmark: string): Text | undefined {
  return isLandmark(landmark) ? t(`result.landmark.${landmark}`) : undefined
}

// A plain line for a refusal or failure reason. A code the app doesn't know gets a general line, never the code.
export function reasonLine(t: Translate, reason: string): Text {
  return t(isReason(reason) ? `reason.${reason}` : 'reason.other')
}

// The next-step tip under a refusal's reason line (M20, Nov 1), for the five reasons that have one; undefined otherwise.
const TIP_REASONS = [
  'no_usable_reference',
  'photo_unusable',
  'water_unsure',
  'no_water_found',
  'references_disagree',
] as const satisfies readonly Reason[]
const isTipReason = (word: string): word is (typeof TIP_REASONS)[number] =>
  (TIP_REASONS as readonly string[]).includes(word)

export function tipLine(t: Translate, reason: string): Text | undefined {
  return isTipReason(reason) ? t(`tip.${reason}`) : undefined
}

// Why a numbered reference wasn't used. A cause the app doesn't know gets a general line, never the code (amendment 2).
export function dropLine(t: Translate, cause: string): Text {
  return t(isDropCause(cause) ? `dropped.${cause}` : 'dropped.other')
}

// One reference of a reading. A dropped one gives its cause and no level, since its level and inches are null
// (amendments 2 and 2a); any other gives where the water meets it, or nothing when its category reads no line.
export function referenceLine(t: Translate, reading: { dropped: string | null; landmark: string | null }): Text | undefined {
  if (reading.dropped !== null) return dropLine(t, reading.dropped)
  return reading.landmark === null ? undefined : landmarkLine(t, reading.landmark)
}

// The count is vehicles and people together, as MS3a's `basis` gives them.
export function basisLine(t: Translate, basis: { vehicles: number; people: number }): Text {
  const count = basis.vehicles + basis.people
  return t(count === 1 ? 'result.basis.one' : 'result.basis.other', { count })
}

// Only called with both ends the API sent, which it does only after the release gate passes (C515).
export function inchesLine(t: Translate, min: number, max: number): Text {
  return min === max ? t('result.inches.same', { min }) : t('result.inches.range', { min, max })
}

// "Measured from the size of the wheel rim." only when geometry set the level (MS3b's C320).
export function levelFromLine(t: Translate, levelFrom?: string): Text | undefined {
  return levelFrom === 'geometry' ? t('result.levelFrom.geometry') : undefined
}
