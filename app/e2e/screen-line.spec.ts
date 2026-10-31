// The screen line is visible and on top on every screen (MS5 Task 18, Review Focus 3). The fixed bar that carries it is
// above Leaflet's panes and controls (z-index 400 to 1,000), but a stacking mistake would hide the line while it stayed
// "in the viewport", so each check asks the browser what is at the line's own points: `document.elementFromPoint` at its
// centre and both ends must return the line itself (or something inside it).
//
// Every route and dialog is visited at 360 x 640 and 390 x 844, in English and Taglish: the map and its list, a pin's
// screen and the flag dialog, Tested and its 18+ check, About, the privacy page, the licences page, and the report flow at
// each step the fake camera, the fake fix and the routes in mocks.ts can reach: the notice, the camera view, the place
// step, sending, waiting, the result, and a problem. The map's OpenStreetMap credit gets the same check on the map and
// on the place step. The page is never scrolled to bring the line into view: it must be there already. The licences page's
// licence texts are never scanned for words (S5-R23); only the line on that page is checked.
import type { Page } from '@playwright/test'
import { expect, LIVE_PIN, test } from './mocks'
import { acceptNotice, label, takePhoto, type Lang } from './steps'

const LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
const SIZES = [
  { width: 360, height: 640 },
  { width: 390, height: 844 },
]
const LANGS: { lang: Lang; name: string }[] = [
  { lang: 'en', name: 'English' },
  { lang: 'fil', name: 'Taglish' },
]

type LineReading = { inView: boolean; onTop: boolean; inDialog: boolean; lang: string | null }

// Every paragraph that is the screen line, as the browser sees it now.
function readLines(page: Page): Promise<LineReading[]> {
  return page.evaluate((line) => {
    const readings: LineReading[] = []
    for (const el of document.querySelectorAll('p')) {
      if (el.textContent?.trim() !== line) continue
      const box = el.getBoundingClientRect()
      const inView =
        box.width > 0 &&
        box.height > 0 &&
        box.top >= 0 &&
        box.left >= 0 &&
        box.bottom <= window.innerHeight &&
        box.right <= window.innerWidth
      const y = box.top + box.height / 2
      const onTop =
        inView &&
        [box.left + box.width / 2, box.left + 2, box.right - 2].every((x) => {
          const hit = document.elementFromPoint(x, y)
          return hit !== null && (hit === el || el.contains(hit))
        })
      readings.push({ inView, onTop, inDialog: el.closest('dialog') !== null, lang: el.getAttribute('lang') })
    }
    return readings
  }, LINE)
}

// The line is inside the viewport and on top, and stays English (C619). An open flag dialog is a modal <dialog> in the
// browser's top layer, over the bar, so it carries its own line (S5-R5): there are two on the page, and the dialog's is the
// one on top.
async function expectLine(page: Page, where: string, dialog = false): Promise<void> {
  const lines = await readLines(page)
  const shown = lines.filter((reading) => reading.inView && reading.onTop)
  expect.soft(shown.length, `${where}: the screen line is inside the viewport and on top`).toBeGreaterThan(0)
  expect.soft(lines.length, `${where}: how many screen lines the page holds`).toBe(dialog ? 2 : 1)
  if (dialog) expect.soft(shown.some((reading) => reading.inDialog), `${where}: the dialog's own line is the one on top`).toBe(true)
  for (const reading of shown) expect.soft(reading.lang, `${where}: the line is marked English`).toBe('en')
}

// The credit of OpenStreetMap's tiles is visible without scrolling, above the screen-line bar, and nothing covers it.
async function expectCredit(page: Page, where: string): Promise<void> {
  const link = page.locator('.leaflet-control-attribution a[href="https://www.openstreetmap.org/copyright"]')
  await expect(link, `${where}: the map's credit is drawn`).toBeVisible()
  await expect(link).toHaveText('© OpenStreetMap contributors')
  const seen = await link.evaluate((a, line) => {
    const box = a.getBoundingClientRect()
    const bar = [...document.querySelectorAll('p')].find((p) => p.textContent?.trim() === line && p.closest('dialog') === null)
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
    return {
      inView: box.top >= 0 && box.left >= 0 && box.bottom <= window.innerHeight && box.right <= window.innerWidth,
      onTop: hit !== null && (hit === a || a.contains(hit)),
      aboveBar: bar !== undefined && box.bottom <= bar.getBoundingClientRect().top + 0.5,
    }
  }, LINE)
  expect.soft(seen.inView, `${where}: the credit is inside the viewport`).toBe(true)
  expect.soft(seen.onTop, `${where}: the credit is on top`).toBe(true)
  expect.soft(seen.aboveBar, `${where}: the credit is above the screen-line bar`).toBe(true)
}

for (const size of SIZES) {
  for (const { lang, name } of LANGS) {
    test(`the screen line is visible and on top on every screen, ${size.width} x ${size.height}, ${name}`, async ({ page, mocks }) => {
      await page.setViewportSize(size)
      await page.addInitScript((chosen) => {
        try {
          localStorage.setItem('lusot.lang', chosen)
        } catch {
          // Without storage the page stays in English; the Taglish run would then fail on its labels, which is the point.
        }
      }, lang)
      const at = (state: string) => `${size.width} x ${size.height}, ${name}, ${state}`
      const button = (key: Parameters<typeof label>[1]) => page.getByRole('button', { name: label(lang, key), exact: true })

      // The map and its list.
      await page.goto('/#/map')
      await expect(page.locator('.map-pin').first()).toBeVisible()
      await expectLine(page, at('#/map, the map'))
      await expectCredit(page, at('#/map, the map'))
      await button('map.list').click()
      await expect(page.getByRole('list', { name: label(lang, 'map.listLabel') })).toBeVisible()
      await expectLine(page, at('#/map, the list'))

      // A pin's own screen, from a pin the map holds, and the flag dialog over it.
      await page.goto(`/#/pin/${LIVE_PIN.id}`)
      await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
      await expectLine(page, at('#/pin/<id>'))
      await button('pin.flag').click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await expectLine(page, at('the flag dialog'), true)
      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).toBeHidden()

      // Tested, and the 18+ check that a sample's first run meets.
      await page.goto('/#/tested')
      await expect(button('sample.run').first()).toBeVisible()
      await expectLine(page, at('#/tested'))
      await button('sample.run').first().click()
      await expect(page.getByRole('heading', { name: label(lang, 'consent.adultTitle') })).toBeVisible()
      await expectLine(page, at('the 18+ check'))
      await button('consent.notNow').click()
      await expect(page.getByRole('heading', { name: label(lang, 'consent.adultTitle') })).toBeHidden()

      // The pages that only read.
      await page.goto('/#/about')
      await expect(page.getByRole('heading', { name: label(lang, 'nav.about'), level: 1 })).toBeVisible()
      await expectLine(page, at('#/about'))
      await page.goto('/#/privacy')
      await expect(page.getByRole('heading', { name: label(lang, 'privacy.title'), level: 1 })).toBeVisible()
      await expectLine(page, at('#/privacy'))
      await page.goto('/#/licences')
      await expect(page.getByRole('heading', { name: label(lang, 'licences.title'), level: 1 })).toBeVisible()
      await expect(page.getByText(label(lang, 'licences.loading'))).toBeHidden()
      await expectLine(page, at('#/licences'))

      // The report flow, step by step. A fresh visit meets the notice first.
      await page.goto('/#/report')
      await expect(page.getByTestId('notice')).toBeVisible()
      await expectLine(page, at('#/report, the notice'))
      await acceptNotice(page, lang)
      await expect(button('camera.shutter')).toBeEnabled()
      await expectLine(page, at('#/report, the camera view'))
      await takePhoto(page, lang)
      await expect(page.getByRole('heading', { name: label(lang, 'place.title') })).toBeVisible()
      await expectLine(page, at('#/report, the place step'))
      await expectCredit(page, at('#/report, the place step'))

      // Sending, held until the test lets the upload through; then waiting, held until the test lets the result through.
      const release = mocks.holdUpload()
      mocks.behaviour.pendingReads = Number.POSITIVE_INFINITY
      await button('place.send').click()
      await expect(page.getByRole('heading', { name: label(lang, 'report.sendingTitle') })).toBeVisible()
      await expectLine(page, at('#/report, sending'))
      release()
      await expect(page.getByRole('heading', { name: label(lang, 'report.waitingTitle') })).toBeVisible()
      await expectLine(page, at('#/report, waiting'))
      mocks.behaviour.pendingReads = 0
      await expect(page.getByRole('heading', { name: label(lang, 'report.resultTitle') })).toBeVisible()
      await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
      await expectLine(page, at('#/report, the result'))

      // A problem: a second photo, and the API pauses uploads.
      mocks.behaviour.upload = 'paused'
      await button('report.newPhoto').click()
      await takePhoto(page, lang)
      await expect(page.getByRole('heading', { name: label(lang, 'place.title') })).toBeVisible()
      await button('place.send').click()
      await expect(page.getByRole('heading', { name: label(lang, 'report.notSent') })).toBeVisible()
      await expectLine(page, at('#/report, a problem'))
    })
  }
}
