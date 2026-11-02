// No sideways swipe at phone width (Rene's device check, Nov 2): at 360 px neither the document nor the scrolling <main>
// is wider than its box on the Tested page, an Ask Lusot answer, About, the licences and the privacy policy. The Tested page
// is the one that failed: a sample's credit line carries a licence URL, which has no space to break at. Every answer is a
// route in mocks.ts.
import type { Page } from '@playwright/test'
import { sampleList } from '../src/mock/fixtures'
import { expect, test } from './mocks'
import { acceptAdult, acceptNotice, label } from './steps'

const L = 'en'
// A credit as a real sample's can read: the licence's name, then its URL in brackets.
const URL_CREDIT = 'Photo: Example Contributor (mock), CC BY 3.0 (https://creativecommons.org/licenses/by/3.0)'
const FIRST = sampleList(1)[0]!

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 })
})

// How far past its box the document, and the <main> that holds the screen, reach to the right. Both must be 0.
async function sideways(page: Page): Promise<{ document: number; main: number }> {
  return page.evaluate(() => {
    const root = document.documentElement
    const main = document.querySelector('main')!
    return { document: root.scrollWidth - root.clientWidth, main: main.scrollWidth - main.clientWidth }
  })
}

async function expectNoSideways(page: Page, where: string): Promise<void> {
  const over = await sideways(page)
  expect(over.document, `${where}: the document is wider than the screen by ${over.document} px`).toBeLessThanOrEqual(0)
  expect(over.main, `${where}: the page is wider than its box by ${over.main} px`).toBeLessThanOrEqual(0)
}

test('the Tested page does not swipe sideways when a sample credit holds a licence URL', async ({ page, mocks }) => {
  mocks.behaviour.sampleCredit = URL_CREDIT
  mocks.behaviour.pins = []
  await page.goto('/#/tested')
  const item = page.getByRole('listitem').filter({ hasText: URL_CREDIT }).first()
  await expect(item).toBeVisible()
  const photo = item.getByRole('img', { name: label(L, 'sample.photoAlt') })
  await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  await expectNoSideways(page, 'Tested, the sample list')
})

test('the Tested page does not swipe sideways once a sample has run, with its credit under the photo', async ({
  page,
  mocks,
}) => {
  // The result card is as wide as the screen, so the licence URL above fits it; this one is a source page's address,
  // whose last piece is longer than the card.
  const credit =
    'Photo: Example Contributor (mock), CC BY 3.0 (https://commons.wikimedia.org/wiki/File:Marikina_flood_Ondoy_2009_street_scene_original.jpg)'
  mocks.behaviour.sampleCredit = credit
  // One sample, so the other cards' credits can't be what reaches past the box.
  mocks.behaviour.sampleCount = 1
  mocks.behaviour.pins = []
  await page.goto('/#/tested')
  const item = page.getByRole('listitem').filter({ hasText: credit })
  await item.getByRole('button', { name: label(L, 'sample.run'), exact: true }).click()
  await acceptAdult(page, L)
  const card = item.locator('article[data-outcome="level"]')
  await expect(card).toBeVisible()
  await expect(card).toContainText(credit)
  // The run's own photo has loaded, so its box has its final size.
  const photo = card.getByRole('img').first()
  await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  await expectNoSideways(page, `Tested, the result card of ${FIRST.sampleId}`)
})

test('Ask Lusot does not swipe sideways when a demo card in its answer has a long credit', async ({ page, mocks }) => {
  mocks.behaviour.askDemoCredit =
    'Photo: Example Contributor (mock), CC BY 3.0 (https://commons.wikimedia.org/wiki/File:Marikina_flood_Ondoy_2009_street_scene_original.jpg)'
  await page.goto('/#/ask')
  await page.getByRole('textbox', { name: label(L, 'ask.ui.questionLabel') }).fill('Gaano kalalim ang baha sa España cor. Maceda?')
  await page.getByRole('button', { name: label(L, 'ask.ui.send'), exact: true }).click()
  await acceptNotice(page, L)
  const answer = page.getByRole('region', { name: label(L, 'ask.ui.answer') })
  await expect(answer.getByText(label(L, 'ask.answer.demo'))).toBeVisible()
  await expect(answer).toContainText(mocks.behaviour.askDemoCredit)
  await expectNoSideways(page, 'Ask Lusot, an answer with a demo card')
})

for (const [route, key, name] of [
  ['/#/about', 'nav.about', 'About'],
  ['/#/licences', 'licences.title', 'Licences'],
  ['/#/privacy', 'privacy.title', 'Privacy'],
] as const) {
  test(`${name} does not swipe sideways`, async ({ page }) => {
    await page.goto(route)
    await expect(page.getByRole('heading', { name: label(L, key), level: 1 })).toBeVisible()
    await expect(page.getByText(label(L, 'licences.loading'))).toBeHidden()
    await expectNoSideways(page, name)
  })
}
