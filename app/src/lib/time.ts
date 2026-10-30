// The times the result card words (plan Table 6): how long ago a photo was taken, and a sample's own date, place and
// event. Each line is built from the string tables, so a Taglish screen gets its own words (C619).
import type { Translate } from '../copy/wording'
import type { Lang, Text } from '../i18n'

const MINUTE_MS = 60_000
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/
// The photos are taken in Metro Manila, so a time is read there whatever time zone the phone is set to.
const MANILA = 'Asia/Manila'

const locale = (lang: Lang) => (lang === 'fil' ? 'fil-PH' : 'en-US')

// "just now" for under a minute or a time in the future, then "25 min ago" and "2 h 5 min ago". A caller gives it a
// time that parses; a time that doesn't reads as "just now" rather than as "NaN min ago".
export function ageText(t: Translate, capturedAt: string, now: Date): Text {
  const minutes = Math.floor((now.getTime() - Date.parse(capturedAt)) / MINUTE_MS)
  if (!(minutes >= 1)) return t('result.age.justNow')
  if (minutes < 60) return t('result.age.minutes', { min: minutes })
  const h = Math.floor(minutes / 60)
  const min = minutes % 60
  return min === 0 ? t('result.age.hours', { h }) : t('result.age.hoursMinutes', { h, min })
}

// A short date such as "Sep 26, 2009", read in Manila. A date-only value (a sample's `date`) is taken as midnight UTC,
// which is 8 AM in Manila, so it keeps its own day. Anything that isn't a date gives nothing.
export function formatDate(lang: Lang, value: string): string | undefined {
  const at = new Date(DATE_ONLY.test(value) ? `${value}T00:00:00Z` : value)
  if (value === '' || Number.isNaN(at.getTime())) return undefined
  return new Intl.DateTimeFormat(locale(lang), {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: MANILA,
  }).format(at)
}

// The photo's time for Details: "Oct 30, 2026, 9:15 AM GMT+8".
export function formatDateTime(lang: Lang, value: string): string | undefined {
  const at = new Date(value)
  if (value === '' || Number.isNaN(at.getTime())) return undefined
  return new Intl.DateTimeFormat(locale(lang), {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: MANILA,
    timeZoneName: 'short',
  }).format(at)
}

// "Photo from Sep 26, 2009, Manila, Typhoon Ondoy" for a sample or a demo pin, which show their photo's own date,
// place and event and no accuracy (spec §4.2). Whatever is missing is left out, and with nothing left there is no line.
export function photoDateLine(
  t: Translate,
  lang: Lang,
  { date, place, event }: { date?: string; place?: string; event?: string },
): Text | undefined {
  const parts = [date === undefined ? undefined : formatDate(lang, date), place?.trim(), event?.trim()].filter(
    (part): part is string => part !== undefined && part !== '',
  )
  return parts.length === 0 ? undefined : t('sample.photoFrom', { parts: parts.join(', ') })
}
