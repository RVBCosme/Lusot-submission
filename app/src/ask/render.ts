// Ask Lusot's answer as the lines a person reads (its spec §4.4, C724). The API sends data only; every word here comes
// from the string tables, and the level and class lines from MS5's own wording functions, so a pin and an answer
// never word one reading two ways. The order is §4.4's: the crossing line first, the summary, the deepest report's
// card, the vehicle line, the other cards, then the demo cards.
import { LEVELS } from '../copy/levels'
import { classHolds, classLine, levelLine, type Translate } from '../copy/wording'
import { makeT, type Text } from '../i18n'
import type { StringKey } from '../i18n/en'
import type { AskAnswer, AskReport } from '../lib/api'
import { ageText, photoDateLine } from '../lib/time'

// A line's source: its own key, or MS5's level line, class line or a demo pin's credit, which have none of their own.
export type LineKey = StringKey | 'level' | 'class' | 'credit'

export type AnswerLine = {
  key: LineKey
  text: Text
  part: 'crossing' | 'summary' | 'card' | 'note' | 'suggestion'
  // A card's lines carry its report's id, and whether the model cited it ("Used") and whether it is a demo pin.
  reportId?: string
  used?: boolean
  demo?: boolean
  // A suggestion's spot, which the screen asks about when it is tapped.
  spot?: string
}

// "safe" in any form and "ligtas" anywhere in a word, the words no Lusot screen shows (CLAUDE.md, MS5's C608).
const BANNED = /[\p{L}\p{N}]*(?:safe|ligtas)[\p{L}\p{N}]*/giu

// A spoken question's transcript as the screen shows it (AskL-Q11's default): each letter of a word that holds a
// banned word becomes "•", and every other word, the place heard among them, stays as Meta heard it.
export function maskBannedWords(text: string): string {
  return text.replace(BANNED, (word) => '•'.repeat(Array.from(word).length))
}

const ONE_LINE: Partial<Record<AskAnswer['kind'], StringKey>> = {
  no_place: 'ask.answer.noPlace',
  lookup_unavailable: 'ask.answer.lookupUnavailable',
  outside_metro_manila: 'ask.answer.outside',
  no_location: 'ask.answer.noLocation',
  off_topic: 'ask.answer.offTopic',
  no_speech: 'ask.answer.noSpeech',
}
const VEHICLE_LINE = {
  light: 'ask.answer.vehicleLight',
  heavy: 'ask.answer.vehicleHeavy',
  on_foot: 'ask.answer.onFoot',
} as const satisfies Record<string, StringKey>

const KNOWN_LEVELS: ReadonlySet<string> = new Set(LEVELS)
// A level MS5 can word, as the client already checks; kept here too, so a card never words a raw code.
const wordable = (report: AskReport) => KNOWN_LEVELS.has(report.level)
// A demo pin shows only with its credit line (MS5's N2).
const credited = (report: AskReport) => report.credit !== undefined && report.credit.trim() !== ''

export function renderAnswer(answer: AskAnswer, t: Translate, now: Date): AnswerLine[] {
  const lines: AnswerLine[] = []
  const here = answer.place?.source === 'here'
  const place = answer.place?.name ?? ''
  const window = (inLang: Translate) => windowText(inLang, answer.windowMin)
  const crossing = (): AnswerLine => ({ key: 'ask.answer.crossing', text: t('ask.answer.crossing'), part: 'crossing' })
  const note = (key: StringKey, part: AnswerLine['part'] = 'note'): AnswerLine => ({ key, text: t(key), part })

  if (answer.crossing) lines.push(crossing())
  const listed = answer.kind === 'reports' || answer.kind === 'no_reports'
  if (answer.source === 'plain_list' && listed) lines.push(note('ask.answer.plainList'))

  const cited = new Set(answer.cited)
  const card = (report: AskReport, key: LineKey, text: Text): AnswerLine => ({
    key,
    text,
    part: 'card',
    reportId: report.id,
    used: cited.has(report.id),
    demo: report.mode === 'demo',
  })
  const where = (report: AskReport) => {
    const key = here ? 'ask.answer.whereHere' : 'ask.answer.where'
    const text = line(t, key, (inLang) => ({ age: ageText(inLang, report.capturedAt, now).text, distance: report.distanceM, place }))
    return card(report, key, text)
  }
  const demoCards = () => {
    for (const report of answer.demo.filter((r) => wordable(r) && credited(r))) {
      lines.push(card(report, 'ask.answer.demo', t('ask.answer.demo')))
      lines.push(card(report, 'level', levelLine(t, report.level, report.levelIsFloor)))
      const photo = t('sample.photoFrom')
      const date = photoDateLine(t, photo.lang, { date: report.capturedAt, place: report.place, event: report.event })
      if (date !== undefined) lines.push(card(report, 'sample.photoFrom', date))
      lines.push(card(report, 'credit', { text: report.credit ?? '', lang: 'en' }))
    }
  }

  switch (answer.kind) {
    case 'reports': {
      const shown = answer.reports.filter(wordable)
      const deepest = shown.find((report) => report.id === answer.deepestId) ?? shown[0]
      const one = answer.count === 1
      const key: StringKey = here
        ? one
          ? 'ask.answer.summaryHereOne'
          : 'ask.answer.summaryHereMany'
        : one
          ? 'ask.answer.summaryOne'
          : 'ask.answer.summaryMany'
      lines.push({ key, text: line(t, key, (inLang) => ({ n: answer.count, place, window: window(inLang) })), part: 'summary' })
      const onFoot = answer.vehicle === 'on_foot'
      if (deepest !== undefined) {
        lines.push(card(deepest, 'level', levelLine(t, deepest.level, deepest.levelIsFloor)))
        // On foot, no class line on any report (plan §9). A PATV or NPLV floor has none either, as on the result card: deeper
        // water could be a worse class. With a heavy vehicle, the crossing line also sits right under the class line, so
        // "not passable to light vehicles" never reads as permission (AskL-Q10); it stays when there is no class line.
        if (!onFoot && classHolds(deepest.level, deepest.levelIsFloor)) {
          lines.push(card(deepest, 'class', classLine(t, deepest.level)))
        }
        if (answer.vehicle === 'heavy') lines.push(card(deepest, 'ask.answer.crossing', t('ask.answer.crossing')))
        lines.push(where(deepest))
      }
      // The vehicle line explains the cards' class lines (or their absence), so it shows only with report cards.
      if (answer.vehicle !== null) lines.push(note(VEHICLE_LINE[answer.vehicle]))
      // The other cards are shorter: the level line and where the photo was taken.
      for (const report of shown.filter((r) => r !== deepest)) {
        lines.push(card(report, 'level', levelLine(t, report.level, report.levelIsFloor)))
        lines.push(where(report))
      }
      demoCards()
      break
    }
    case 'no_reports': {
      const key = here ? 'ask.answer.noReportsHere' : 'ask.answer.noReports'
      lines.push({ key, text: line(t, key, (inLang) => ({ place, window: window(inLang) })), part: 'summary' })
      lines.push(note('ask.answer.noReportNote'))
      demoCards()
      break
    }
    case 'place_too_broad':
      lines.push(note('ask.answer.tooBroad', 'summary'))
      for (const spot of answer.suggestions) {
        lines.push({ key: 'ask.ui.suggestionQuestion', text: t('ask.ui.suggestionQuestion', { spot }), part: 'suggestion', spot })
      }
      break
    default: {
      const key = ONE_LINE[answer.kind]
      if (key !== undefined) lines.push(note(key, 'summary'))
    }
  }
  return lines
}

// A line with its {name}s filled in the line's own language: on a Taglish screen an unreviewed screen-line key shows
// in English (C619), so the age and the window inside it must be English too.
function line(t: Translate, key: StringKey, vars: (inLang: Translate) => Record<string, string | number>): Text {
  const inLang = makeT(t(key).lang)
  return inLang(key, vars(inLang))
}

// "3 hours", "1 hour", "90 minutes" or "1 minute".
function windowText(t: Translate, minutes: number): string {
  if (minutes % 60 === 0) {
    const hours = minutes / 60
    return (hours === 1 ? t('ask.window.hour') : t('ask.window.hours', { n: hours })).text
  }
  return (minutes === 1 ? t('ask.window.minute') : t('ask.window.minutes', { n: minutes })).text
}
