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

// Whether a key shows its English line in `lang`: always in English, and on a Taglish screen for the two locked lines
// and every screen-line key whose Taglish isn't reviewed yet.
export function showsEnglish(lang: Lang, key: StringKey): boolean {
  return lang === 'en' || LOCKED.includes(key) || (SCREEN_LINE_PREFIXES.some((p) => key.startsWith(p)) && !FIL[key].reviewed)
}

// The text a person sees for a key, with {name} filled from `vars`.
export function label(lang: Lang, key: StringKey, vars: Record<string, string | number> = {}): string {
  const text = showsEnglish(lang, key) ? EN[key].text : FIL[key].text
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

// The 18+ check alone, before a sample's first run: the box, then "Continue".
export async function acceptAdult(page: Page, lang: Lang): Promise<void> {
  await expect(page.getByRole('heading', { name: label(lang, 'consent.adultTitle') })).toBeVisible()
  await page.getByRole('checkbox', { name: label(lang, 'consent.adult') }).check()
  await page.getByRole('button', { name: label(lang, 'consent.continue'), exact: true }).click()
}

// A fresh #/report, its notice, the fake camera's still and the place step with the fake fix, ready for "Send".
export async function toPlaceStep(page: Page, lang: Lang): Promise<void> {
  await page.goto('/#/report')
  await acceptNotice(page, lang)
  await takePhoto(page, lang)
  await expect(page.getByRole('heading', { name: label(lang, 'place.title') })).toBeVisible()
}

// "Send" on the place step.
export async function send(page: Page, lang: Lang): Promise<void> {
  await page.getByRole('button', { name: label(lang, 'place.send'), exact: true }).click()
}

// The person's own result: the result screen's heading and its card.
export async function expectResult(page: Page, lang: Lang, outcome: string): Promise<void> {
  await expect(page.getByRole('heading', { name: label(lang, 'report.resultTitle') })).toBeVisible()
  await expect(page.locator(`article[data-outcome="${outcome}"]`)).toBeVisible()
}

// Sets the language and theme before the app reads them, for every page this test opens.
export async function choose(page: Page, choice: { lang?: Lang; theme?: 'light' | 'dark' }): Promise<void> {
  await page.addInitScript((chosen) => {
    try {
      if (chosen.lang !== undefined) localStorage.setItem('lusot.lang', chosen.lang)
      if (chosen.theme !== undefined) localStorage.setItem('lusot.theme', chosen.theme)
    } catch {
      // Without storage the page keeps its defaults; the test's labels then fail, which is the point.
    }
  }, choice)
}
