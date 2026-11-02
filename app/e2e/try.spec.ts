// "Try your own photo" on the Tested page (C534, C640), all mocked: a photo chosen from the device goes through POST /try,
// the S3 stand-in and the poll to a result card that only the person sees. It never reaches the map, and never uses the
// report flow's POST /uploads. A pause reads as a pause, and the screen line stays on the page with the card. Every answer
// is a route in mocks.ts.
import type { Page } from '@playwright/test'
import { expect, test, TRY_PHOTO, type Mocks } from './mocks'
import { expectLine } from './screenLine'
import { acceptNotice, label } from './steps'

const L = 'en'
const tries = (mocks: Mocks) => mocks.requests.filter((r) => r.method === 'POST' && r.path === '/try')
// The photo's POST to the S3 stand-in, for the try report only.
const toS3 = (mocks: Mocks) => mocks.requests.filter((r) => r.method === 'POST' && r.path.startsWith('/uploads/'))

// The Tested page, "Choose a photo", the notice gate, then the photo into the page's one file input. The input is out of
// the accessibility tree (aria-hidden), so it is found by its type, not by its label. setInputFiles stands in for the
// system's picker, which a test can't see.
async function choosePhoto(page: Page): Promise<void> {
  await page.goto('/#/tested')
  await page.getByRole('button', { name: label(L, 'try.choose'), exact: true }).click()
  await acceptNotice(page, L)
  await page.locator('input[type=file]').setInputFiles({ name: 'flood.png', mimeType: 'image/png', buffer: TRY_PHOTO })
}

const section = (page: Page) => page.getByRole('region', { name: label(L, 'tested.try.title') })

test('choose a photo on Tested → the try card with its verdict and "Only you see this result", and no POST /uploads or map pin', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.pins = []
  await choosePhoto(page)
  const card = section(page).locator('article[data-outcome="level"]')
  await expect(card).toBeVisible()
  await expect(card).toContainText(label(L, 'verdict.nplv'))
  await expect(card).toContainText(new RegExp(`${label(L, 'result.levelName.knee')} deep at this spot`, 'i'))
  await expect(card).toContainText(label(L, 'result.try'))
  // The run's start is not a capture time, and a chosen photo has no place: the card says neither.
  await expect(card).not.toContainText('Photo taken')
  await expect(card).not.toContainText('Location within')
  await expect(section(page).getByRole('button', { name: label(L, 'try.chooseAnother'), exact: true })).toBeVisible()

  // One POST /try with only the consent version, then the photo to S3 after the policy's fields; the report flow's
  // POST /uploads is never used.
  expect(tries(mocks)).toHaveLength(1)
  expect(tries(mocks)[0]!.headers['x-lusot-device']).not.toBe('')
  expect(Object.keys((tries(mocks)[0]!.json ?? {}) as object)).toEqual(['consentVersion'])
  expect(toS3(mocks)).toHaveLength(1)
  expect(toS3(mocks)[0]!.formFields?.at(-1)).toBe('file')
  expect(mocks.requests.filter((r) => r.path === '/uploads')).toHaveLength(0)

  // A chosen photo's result never reaches the map: it holds no pin of the person's own.
  await page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.map'), exact: true }).click()
  await expect(page.getByRole('heading', { name: label(L, 'map.empty.title') })).toBeVisible()
  await expect(page.getByRole('button', { name: new RegExp(`^${label(L, 'map.own')}\\.`) })).toHaveCount(0)
})

test('paused: POST /try answers 503 model_calls_paused → the paused notice, never an error', async ({ page, mocks }) => {
  mocks.behaviour.tryRun = 'model_calls_paused'
  await choosePhoto(page)
  await expect(section(page)).toContainText(label(L, 'result.paused'))
  await expect(section(page)).not.toContainText(label(L, 'result.failed'))
  await expect(section(page)).not.toContainText(label(L, 'try.sendFailed'))
  // The Tested page is where this is, so the paused line links to the map only.
  await expect(section(page).getByRole('link', { name: label(L, 'nav.map'), exact: true })).toBeVisible()
  await expect(section(page).getByRole('link', { name: label(L, 'nav.tested'), exact: true })).toHaveCount(0)
  expect(tries(mocks)).toHaveLength(1)
  expect(toS3(mocks)).toHaveLength(0)
})

test("a day's cap: POST /try answers 429 daily_cap → its line, and the person may choose another photo", async ({
  page,
  mocks,
}) => {
  mocks.behaviour.tryRun = 'daily_cap'
  await choosePhoto(page)
  await expect(section(page)).toContainText(label(L, 'try.limit.daily_cap'))
  await expect(section(page).getByRole('button', { name: label(L, 'try.chooseAnother'), exact: true })).toBeVisible()
  expect(toS3(mocks)).toHaveLength(0)
})

test('the screen line shows on the Tested page with the try card', async ({ page, mocks }) => {
  mocks.behaviour.pins = []
  await choosePhoto(page)
  await expect(section(page).locator('article[data-outcome="level"]')).toBeVisible()
  await expectLine(page, 'Tested page, with the try card')
})
