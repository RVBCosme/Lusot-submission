// What a marker and a list row say about a pin: its level line and its age, and nothing else (Task 13's privacy rule:
// no position, no id, no place, no accuracy). A demo pin gives its photo's date where a live pin gives its age.
import { levelLine, type Translate } from '../copy/wording'
import type { Lang, Text } from '../i18n'
import type { Pin } from '../lib/api'
import { ageText, formatDate } from '../lib/time'
import { isOwn } from './pins'

export type PinLines = { level: Text; when: Text | undefined }

export function pinLines(t: Translate, lang: Lang, pin: Pin, now: Date): PinLines {
  const level = levelLine(t, pin.level, pin.levelIsFloor)
  if (pin.mode === 'demo') {
    const date = formatDate(lang, pin.capturedAt)
    return { level, when: date === undefined ? undefined : t('sample.photoFrom', { parts: date }) }
  }
  return { level, when: t('result.photoTaken', { age: ageText(t, pin.capturedAt, now).text }) }
}

// A marker's name for a screen reader: "Demo." or "Your report.", then the level line, then the age or the date.
export function pinLabel(t: Translate, lang: Lang, pin: Pin, now: Date): string {
  const { level, when } = pinLines(t, lang, pin, now)
  const mark = isOwn(pin) ? `${t('map.own').text}.` : pin.mode === 'demo' ? `${t('badge.demo').text}.` : undefined
  return [mark, level.text, when?.text].filter((part) => part !== undefined).join(' ')
}
