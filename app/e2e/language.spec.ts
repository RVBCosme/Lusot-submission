// The Taglish switch (MS5 Task 18, C619): switching changes the visible lines and the page's language, keeps the screen
// line and "Not affiliated with MMDA." in English, and marks every English line on a Taglish screen lang="en", so a
// screen reader says it in English (WCAG 2.2's language of parts). The lines that stay English are the app's own rule
// (app/src/i18n/index.tsx), which e2e/steps.ts's `label` repeats.
import type { Page } from '@playwright/test'
import { EN, type StringKey } from '../src/i18n/en'
import { FIL } from '../src/i18n/fil'
import { expect, LIVE_PIN, test } from './mocks'
import { expectLine } from './screenLine'
import { acceptNotice, label, showsEnglish } from './steps'

// The whole lines a Taglish screen shows in English, with no {placeholder} left in them: the screen line, "Not
// affiliated with MMDA." and any screen-line key whose Taglish is still unreviewed.
const ENGLISH_ON_TAGLISH = (Object.keys(EN) as StringKey[])
  .filter((key) => showsEnglish('fil', key) && !EN[key].text.includes('{'))
  .map((key) => EN[key].text)

// Every text node on the page that is one of those lines, and the language its nearest lang attribute gives it.
async function unmarked(page: Page): Promise<string[]> {
  return page.evaluate((lines) => {
    const wanted = new Set(lines)
    const found: string[] = []
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
      const text = node.textContent?.trim() ?? ''
      if (!wanted.has(text)) continue
      const lang = node.parentElement?.closest('[lang]')?.getAttribute('lang')
      if (lang !== 'en') found.push(`${text} (lang=${lang ?? 'none'})`)
    }
    return found
  }, ENGLISH_ON_TAGLISH)
}

test('switching to Taglish changes the lines, keeps the screen line in English, and marks English lines', async ({
  page,
}) => {
  expect(ENGLISH_ON_TAGLISH.length, 'some lines stay English on a Taglish screen').toBeGreaterThan(0)
  await page.goto('/#/map')
  const nav = page.getByRole('navigation')
  await expect(nav.getByRole('link', { name: label('en', 'nav.report'), exact: true })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')

  await page.getByRole('group', { name: label('en', 'lang.switch') }).getByRole('button', { name: label('en', 'lang.fil') }).click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'fil')
  // The visible lines change: the navigation and the map's heading are Taglish now.
  for (const key of ['nav.map', 'nav.report', 'nav.about'] as const) {
    if (FIL[key].text !== EN[key].text) await expect(nav).toContainText(FIL[key].text)
  }
  await expect(page.getByRole('heading', { name: label('fil', 'map.empty.title') }).or(page.locator('.map-pin').first())).toBeVisible()
  await expectLine(page, 'Taglish, #/map')
  expect(await unmarked(page), '#/map').toEqual([])

  // The choice is kept on the phone.
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'fil')

  // Each screen in Taglish: the screen line stays English and on top, and every English line is marked.
  const screens: [string, () => Promise<void>][] = [
    ['#/pin/<id>', async () => {
      await page.goto(`/#/pin/${LIVE_PIN.id}`)
      await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
    }],
    ['#/tested', async () => {
      await page.goto('/#/tested')
      await expect(page.getByRole('heading', { name: label('fil', 'nav.tested'), level: 1 })).toBeVisible()
    }],
    ['#/about', async () => {
      await page.goto('/#/about')
      await expect(page.getByRole('heading', { name: label('fil', 'nav.about'), level: 1 })).toBeVisible()
      // "Not affiliated with MMDA." stays English, and is marked.
      await expect(page.getByText(EN['about.notAffiliated'].text).first()).toHaveAttribute('lang', 'en')
    }],
    ['#/privacy', async () => {
      await page.goto('/#/privacy')
      await expect(page.getByRole('heading', { name: label('fil', 'privacy.title'), level: 1 })).toBeVisible()
      // The policy is English until Rene approves its Taglish (C605), and says so to a screen reader.
      await expect(page.getByTestId('policy')).toHaveAttribute('lang', 'en')
    }],
    ['#/report, the notice', async () => {
      await page.goto('/#/report')
      await expect(page.getByTestId('notice')).toBeVisible()
      // The notice's prose is English until Rene approves its Taglish, and says so to a screen reader.
      await expect(page.getByTestId('notice')).toHaveAttribute('lang', 'en')
    }],
    ['#/report, the camera', async () => {
      await acceptNotice(page, 'fil')
      await expect(page.getByRole('heading', { name: label('fil', 'camera.title') })).toBeVisible()
    }],
  ]
  for (const [where, open] of screens) {
    await open()
    await expectLine(page, `Taglish, ${where}`)
    expect(await unmarked(page), where).toEqual([])
  }

  // And back to English: the page's language follows.
  await page.getByRole('group', { name: label('fil', 'lang.switch') }).getByRole('button', { name: label('fil', 'lang.en') }).click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.getByRole('heading', { name: label('en', 'camera.title') })).toBeVisible()
})
