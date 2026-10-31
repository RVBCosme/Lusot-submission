// A weak signal (MS5 Task 18, C635, W24): the photo's POST to S3 fails once and goes through on its one retry, with the
// same link, so the photo is analysed once; and with every answer 3 s late, the flow still ends on its result card.
// CDP's network throttling doesn't slow answers that `context.route` fulfils, so mocks.ts holds each answer instead.
import { expect, OWN_ID, test } from './mocks'
import { expectResult, label, send, toPlaceStep } from './steps'

const L = 'en'

test('the S3 upload fails once and goes through on the retry, with the same link', async ({ page, mocks }) => {
  mocks.behaviour.s3Failures = 1
  await toPlaceStep(page, L)
  await send(page, L)
  await expectResult(page, L, 'level')
  expect(mocks.requests.filter((r) => r.method === 'POST' && r.path === '/uploads'), 'one upload link').toHaveLength(1)
  expect(mocks.requests.filter((r) => r.method === 'POST' && r.path === `/uploads/${OWN_ID}`), 'two tries').toHaveLength(2)
})

test('with every answer 3 s late, the flow still ends on its result card', async ({ page, mocks }) => {
  test.slow()
  mocks.behaviour.delayMs = 3000
  mocks.behaviour.pendingReads = 1
  await toPlaceStep(page, L)
  await send(page, L)
  await expect(page.getByRole('heading', { name: label(L, 'report.sendingTitle') })).toBeVisible()
  // About 17 s of held answers: the upload and its preflight, S3, and two reads of the report.
  await expect(page.getByRole('heading', { name: label(L, 'report.resultTitle') })).toBeVisible({ timeout: 60_000 })
  await expectResult(page, L, 'level')
  await expect(page.locator('article[data-outcome="level"]')).toContainText(
    new RegExp(`${label(L, 'result.levelName.knee')} deep at this spot`, 'i'),
  )
})
