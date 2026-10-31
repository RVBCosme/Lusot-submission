// P1's live half (MS7 Task 10, spec P1): on the site that LUSOT_LIVE_URL names, with empty storage, each control that
// would spend Meta credits stops at its gate first (C605). "Run this sample" stops at the 18+ check, "Report" at the
// consent notice, and Ask Lusot's first question at the notice too. No gate is passed: the boxes stay unticked, and
// the guard aborts any request that isn't a read, so a gate that failed open would fail the test without reaching Meta.
//
// Skipped unless LUSOT_LIVE_URL is set. A step the site can't show (no sample listed, a build with no API) is skipped
// and says why.
import { expect, test } from '@playwright/test'
import { guardWrites, LIVE_URL, SKIP_REASON } from './live'
import { label } from './steps'

test.skip(LIVE_URL === '', SKIP_REASON)

const L = 'en' as const

test('with empty storage, "Run this sample" stops at the 18+ check', async ({ page }) => {
  const stopped = await guardWrites(page)
  await page.goto('#/tested')
  const run = page.getByRole('button', { name: label(L, 'sample.run'), exact: true })
  const noApi = page.getByText(label(L, 'tested.samples.noApi'), { exact: true })
  const more = page.getByText(label(L, 'tested.samples.more'), { exact: true })
  // The list has loaded once a sample's button, the short list's line or the no-API line shows.
  await expect(run.or(more).or(noApi).first()).toBeVisible()
  test.skip((await run.count()) === 0, 'the site lists no sample to run')

  await run.first().click()
  await expect(page.getByRole('heading', { name: label(L, 'consent.adultTitle'), exact: true })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: label(L, 'consent.adult') })).not.toBeChecked()
  await expect(page.getByRole('button', { name: label(L, 'consent.continue'), exact: true })).toBeDisabled()
  await expect(page.getByTestId('notice'), 'a sample asks the 18+ check alone, not the notice').toBeHidden()
  await page.waitForTimeout(1_000) // room for a request that should never come
  expect(stopped, 'every request was a read').toEqual([])
})

test('with empty storage, "Report" stops at the consent notice', async ({ page }) => {
  const stopped = await guardWrites(page)
  await page.goto('#/map')
  const report = page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.report'), exact: true })
  await expect(report).toBeVisible()
  // A build with no API disables Report (MS1's R31); a typed #/report must still meet the notice.
  if ((await report.getAttribute('aria-disabled')) === 'true') await page.goto('#/report')
  else await report.click()

  await expect(page.getByTestId('notice')).toBeVisible()
  await expect(page.getByRole('checkbox', { name: label(L, 'consent.adult') })).not.toBeChecked()
  await expect(page.getByRole('button', { name: label(L, 'consent.continue'), exact: true })).toBeDisabled()
  // The camera isn't drawn behind the notice (S5-R10).
  await expect(page.getByRole('heading', { name: label(L, 'camera.title') })).toBeHidden()
  await page.waitForTimeout(1_000)
  expect(stopped, 'every request was a read').toEqual([])
})

test("with empty storage, Ask Lusot's first question stops at the consent notice", async ({ page }) => {
  const stopped = await guardWrites(page)
  await page.goto('#/ask')
  const box = page.getByLabel(label(L, 'ask.ui.questionLabel'), { exact: true })
  const noApi = page.getByText(label(L, 'ask.ui.noApi'), { exact: true })
  await expect(box.or(noApi).first()).toBeVisible()
  test.skip((await box.count()) === 0, 'this build has no API, so Ask Lusot takes no question')

  await box.fill(label(L, 'ask.ui.example3'))
  await page.getByRole('button', { name: label(L, 'ask.ui.send'), exact: true }).click()
  await expect(page.getByTestId('notice')).toBeVisible()
  await expect(page.getByRole('checkbox', { name: label(L, 'consent.adult') })).not.toBeChecked()
  await page.waitForTimeout(1_000)
  expect(stopped, 'every request was a read').toEqual([])
})
