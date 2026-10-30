// The copy-review table (C609, M20): every line of both string tables, ordered by the screen that shows it, as one
// Markdown table for Rene. `npm run copy:table -w app` prints it.
import { EN, type Entry } from '../i18n/en'
import { FIL } from '../i18n/fil'

// Where a screen-line key sits when its name holds no screen of its own: 'reason.too_dark' is shown on the
// result, 'retake.tip' on the report flow.
const SCREEN_OF_PREFIX: Record<string, string> = {
  refusal: 'result',
  reason: 'result',
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

// A key names its screen as its first part, or, after a screen-line prefix, as the part that follows it when
// the key has a third part ('refusal.sample.cantTell' is on 'sample'; 'refusal.d19' on the result).
export function screenOf(key: string): string {
  const parts = key.split('.')
  const first = parts[0]
  if (!Object.hasOwn(SCREEN_OF_PREFIX, first)) return first
  return parts.length >= 3 ? parts[1] : SCREEN_OF_PREFIX[first]
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
