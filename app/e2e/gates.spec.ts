// The two gates come before anything calls Meta (MS5 Task 18, C605, U8): "Run this sample" stops at the 18+ check, and
// "Report" at the consent notice, until each is accepted; a typed #/report meets the notice too. Every answer is a route
// in mocks.ts, which counts the paid requests (POST /samples/{id} and POST /uploads) a gate must hold back.
import { expect, test, type Mocks } from './mocks'
import { acceptAdult, acceptNotice, label } from './steps'

const L = 'en'
const runs = (mocks: Mocks) => mocks.requests.filter((r) => r.method === 'POST' && r.path.startsWith('/samples/')).length
const uploads = (mocks: Mocks) => mocks.requests.filter((r) => r.method === 'POST' && r.path === '/uploads').length

test('"Run this sample" stops at the 18+ check until it is accepted', async ({ page, mocks }) => {
  await page.goto('/#/tested')
  const run = page.getByRole('button', { name: label(L, 'sample.run'), exact: true }).first()
  await run.click()
  await expect(page.getByRole('heading', { name: label(L, 'consent.adultTitle') })).toBeVisible()
  // "Continue" stays off until the box is ticked, and "Not now" runs nothing.
  await expect(page.getByRole('button', { name: label(L, 'consent.continue'), exact: true })).toBeDisabled()
  await page.getByRole('button', { name: label(L, 'consent.notNow'), exact: true }).click()
  await expect(page.getByRole('heading', { name: label(L, 'consent.adultTitle') })).toBeHidden()
  expect(runs(mocks), 'no sample ran before the 18+ check').toBe(0)

  await run.click()
  await acceptAdult(page, L)
  await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
  expect(runs(mocks), 'the sample ran once, after the 18+ check').toBe(1)
})

test('"Report" stops at the consent notice until it is accepted, and the 18+ check alone is not the notice', async ({
  page,
  mocks,
}) => {
  // The 18+ check, passed on the Tested page, doesn't stand in for the notice.
  await page.goto('/#/tested')
  await page.getByRole('button', { name: label(L, 'sample.run'), exact: true }).first().click()
  await acceptAdult(page, L)
  await expect(page.locator('article[data-outcome="level"]')).toBeVisible()

  await page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.report'), exact: true }).click()
  await expect(page.getByTestId('notice')).toBeVisible()
  await expect(page.getByRole('heading', { name: label(L, 'camera.title') })).toBeHidden()
  // Leaving the notice unanswered uploads nothing.
  await page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.map'), exact: true }).click()
  await page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.report'), exact: true }).click()
  await expect(page.getByTestId('notice')).toBeVisible()
  expect(uploads(mocks)).toBe(0)

  await acceptNotice(page, L)
  await expect(page.getByRole('heading', { name: label(L, 'camera.title') })).toBeVisible()
  // Once accepted, the notice isn't asked again on this phone.
  await page.reload()
  await expect(page.getByRole('heading', { name: label(L, 'camera.title') })).toBeVisible()
  await expect(page.getByTestId('notice')).toBeHidden()
})

test('a fresh visit typed straight to #/report shows the notice, with nothing behind it', async ({ page, mocks }) => {
  await page.goto('/#/report')
  await expect(page.getByTestId('notice')).toBeVisible()
  await expect(page.getByRole('button', { name: label(L, 'camera.shutter') })).toBeHidden()
  // The camera isn't opened behind the notice: no video element plays.
  await expect(page.locator('video')).toHaveCount(0)
  expect(uploads(mocks)).toBe(0)
})
