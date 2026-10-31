// What the specs share: the words on screen, read from the app's own string tables so a test never types a line twice,
// and the first steps of the report flow.
import { expect, type Page } from '@playwright/test'
import { EN, type StringKey } from '../src/i18n/en'
import { FIL } from '../src/i18n/fil'

export type Lang = 'en' | 'fil'

// The two lines that stay in English in both languages (C619), and the keys whose Taglish shows English until it is
// reviewed. These are the rules in app/src/i18n/index.tsx (resolveText), which can't be imported here: it is a React module.
const LOCKED: readonly StringKey[] = ['layout.screenLine', 'about.notAffiliated']
const SCREEN_LINE_PREFIXES = ['refusal.', 'reason.', 'retake.', 'consent.', 'privacy.', 'ask.answer.']

// The text a person sees for a key, with {name} filled from `vars`.
export function label(lang: Lang, key: StringKey, vars: Record<string, string | number> = {}): string {
  const english = lang === 'en' || LOCKED.includes(key) || (SCREEN_LINE_PREFIXES.some((p) => key.startsWith(p)) && !FIL[key].reviewed)
  const text = english ? EN[key].text : FIL[key].text
  return text.replace(/\{(\w+)\}/g, (placeholder, name: string) => (name in vars ? String(vars[name]) : placeholder))
}

// Goes past the consent notice on #/report: the 18+ box, then "Continue".
export async function acceptNotice(page: Page, lang: Lang): Promise<void> {
  await page.getByRole('checkbox', { name: label(lang, 'consent.adult') }).check()
  await page.getByRole('button', { name: label(lang, 'consent.continue'), exact: true }).click()
}

// The camera's shutter, pressed once the fake camera's first frame has arrived (the button is disabled until then).
export async function takePhoto(page: Page, lang: Lang): Promise<void> {
  const shutter = page.getByRole('button', { name: label(lang, 'camera.shutter'), exact: true })
  await expect(shutter).toBeEnabled()
  await shutter.click()
}
