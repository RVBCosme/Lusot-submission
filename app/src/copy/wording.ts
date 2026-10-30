// Every line a result can show, built from the string tables so a Taglish screen marks an English fallback
// lang="en" (C619). Each function takes the `t` of makeT or useT and returns a Text. The words live in
// i18n/en.ts and fil.ts; this file only picks the line and fills its numbers. Models never output inches: the app
// words what the API sends (CLAUDE.md).
import type { makeT, Text } from '../i18n'
import {
  BODY_FLOORS,
  FAILED_REASONS,
  OFF_GAUGE,
  PASSABILITY,
  PEOPLE_LANDMARKS,
  REFUSED_REASONS,
  WHEEL_LANDMARKS,
  type Landmark,
  type Level,
  type Reason,
} from './levels'

export type Translate = ReturnType<typeof makeT>

const LANDMARKS: readonly string[] = [...WHEEL_LANDMARKS, ...PEOPLE_LANDMARKS, ...BODY_FLOORS]
const REASONS: readonly string[] = [...REFUSED_REASONS, ...FAILED_REASONS]

const isLandmark = (word: string): word is Landmark => LANDMARKS.includes(word)
const isReason = (word: string): word is Reason => REASONS.includes(word)

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
