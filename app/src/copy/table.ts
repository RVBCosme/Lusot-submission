// The copy-review table (C609, M20): every line of both string tables, ordered by the screen that shows it, as one
// Markdown table for Rene. `npm run copy:table -w app` prints it.
import { makeT } from '../i18n'
import { EN, type Entry } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { LEVELS } from './levels'
import { levelLine } from './wording'

// Where a screen-line key sits when its name holds no screen of its own: 'reason.too_dark' is shown on the
// result, 'retake.tip' on the report flow.
const SCREEN_OF_PREFIX: Record<string, string> = {
  refusal: 'result',
  reason: 'result',
  tip: 'result',
  verdict: 'result',
  depth: 'result',
  retake: 'report',
  consent: 'consent',
  privacy: 'privacy',
}

// The order the screens appear in the app. A screen not listed comes after these, by name.
const SCREEN_ORDER = [
  'nav',
  'layout',
  'lang',
  'report',
  'result',
  'sample',
  'map',
  'pin',
  'tested',
  'about',
  'consent',
  'privacy',
  'licences',
]

// A key names its screen as its first part. After refusal., reason. or retake., a third part that is a listed
// screen names it instead ('refusal.sample.someoneWouldSee' is on 'sample'); any other key of those prefixes sits on
// the screen that shows it ('refusal.d19' on the result). consent. and privacy. are screens themselves, so a
// longer key ('consent.adult.label') stays on its own.
export function screenOf(key: string): string {
  const parts = key.split('.')
  const first = parts[0]
  if (!Object.hasOwn(SCREEN_OF_PREFIX, first)) return first
  const home = SCREEN_OF_PREFIX[first]
  if (home === first) return home
  return parts.length >= 3 && SCREEN_ORDER.includes(parts[1]) ? parts[1] : home
}

const cell = (text: string) => text.replaceAll('|', '\\|').replace(/\s*\r?\n\s*/g, ' ')

function rank(screen: string): number {
  const place = SCREEN_ORDER.indexOf(screen)
  return place === -1 ? SCREEN_ORDER.length : place
}

const mark = (reviewed: boolean) => (reviewed ? 'yes' : 'no')

export function copyTable(english: Record<string, Entry> = EN, taglish: Record<string, Entry> = FIL): string {
  const keys = Object.keys(english)
    .map((key, order) => ({ key, order, screen: screenOf(key) }))
    // Equal ranks are one listed screen or several unlisted ones, which go by name; within a screen, table order.
    .sort((a, b) => rank(a.screen) - rank(b.screen) || a.screen.localeCompare(b.screen) || a.order - b.order)
  const rows = keys.map(({ key }) => {
    const en = english[key]
    const fil = taglish[key]
    return `| \`${key}\` | ${cell(en.text)} | ${cell(fil.text)} | en ${mark(en.reviewed)}, fil ${mark(fil.reviewed)} |`
  })
  return ['| Key | English | Taglish | Reviewed |', '| --- | --- | --- | --- |', ...rows].join('\n')
}

// The level lines as people read them: each of the 9 levels in its template, in both languages, and the one floor
// the rules reach (every floor is at tire). The table above lists the templates and the names apart, so this is
// where Rene reads the whole line and sees how its capital letter falls.
export function levelLineTable(): string {
  const en = makeT('en')
  const fil = makeT('fil')
  const rows = [
    ...LEVELS.map((level) => ({ label: `\`${level}\``, level, isFloor: false })),
    { label: '`tire`, at least', level: 'tire' as const, isFloor: true },
  ].map(({ label, level, isFloor }) => {
    return `| ${label} | ${cell(levelLine(en, level, isFloor).text)} | ${cell(levelLine(fil, level, isFloor).text)} |`
  })
  return ['| Level | English | Taglish |', '| --- | --- | --- |', ...rows].join('\n')
}
