// The samples on the Tested page (MS5 Task 18, C617, C637, U7): a sample from the list to its result card, with its
// photo and credit; a run while analysis is paused, which shows the saved result with its date (amendment 10); a run
// that refuses, in C637's frame; and a short or failed list, which says "More samples coming." and shows no error
// (amendment 11). A sample's result never reaches the map. Every answer is a route in mocks.ts.
import { sampleList } from '../src/mock/fixtures'
import { expect, test, type Mocks } from './mocks'
import { acceptAdult, label } from './steps'

const L = 'en'
const FIRST = sampleList(1)[0]!
const runs = (mocks: Mocks) => mocks.requests.filter((r) => r.method === 'POST' && r.path.startsWith('/samples/'))

test('a sample from the list to its result card, with its photo and credit, and never a pin', async ({ page, mocks }) => {
  mocks.behaviour.pins = []
  await page.goto('/#/tested')
  const item = page.getByRole('listitem').filter({ hasText: FIRST.credit })
  await expect(item).toBeVisible()
  // Before it runs: the blurred photo, its place, date and event, and its credit line.
  const photo = item.getByRole('img', { name: label(L, 'sample.photoAlt') })
  await expect(photo).toBeVisible()
  await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  await expect(item).toContainText(FIRST.place)
  await expect(item).toContainText(FIRST.event!)
  await expect(item).toContainText(label(L, 'sample.edited'))

  await item.getByRole('button', { name: label(L, 'sample.run'), exact: true }).click()
  await acceptAdult(page, L)
  const card = item.locator('article[data-outcome="level"]')
  await expect(card).toBeVisible()
  expect(runs(mocks)).toHaveLength(1)
  expect(runs(mocks)[0]!.headers['x-lusot-device']).not.toBe('')
  await expect(card).toContainText(label(L, 'badge.sample'))
  await expect(card).toContainText(new RegExp(`${label(L, 'result.levelName.knee')} deep at this spot`, 'i'))
  await expect(card).toContainText(label(L, 'sample.liveReading'))
  await expect(card).toContainText(FIRST.credit)

  // `run twice starts one sample` (Review Focus 1): with the 18+ check passed, a double tap on the next sample is one run.
  const second = page.getByRole('listitem').filter({ hasText: sampleList(2)[1]!.credit })
  await second.getByRole('button', { name: label(L, 'sample.run'), exact: true }).dblclick()
  await expect(second.locator('article[data-outcome="level"]')).toBeVisible()
  expect(runs(mocks)).toHaveLength(2)

  // A sample's result never reaches the map: it holds no pin of the person's own.
  await page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.map'), exact: true }).click()
  await expect(page.getByRole('heading', { name: label(L, 'map.empty.title') })).toBeVisible()
  await expect(page.getByRole('button', { name: new RegExp(`^${label(L, 'map.own')}\\.`) })).toHaveCount(0)
})

test('while analysis is paused, a sample shows the paused line and then its saved result, with its date', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.sampleRun = 'saved'
  await page.goto('/#/tested')
  const item = page.getByRole('listitem').filter({ hasText: FIRST.credit })
  await item.getByRole('button', { name: label(L, 'sample.run'), exact: true }).click()
  await acceptAdult(page, L)
  const card = item.locator('article[data-outcome="level"]')
  await expect(card).toBeVisible()
  await expect(card).toContainText(label(L, 'result.paused'))
  await expect(card).toContainText(label(L, 'sample.savedFrom', { date: 'Oct 29, 2026' }))
  await expect(card).toContainText(label(L, 'sample.savedReading'))
  await expect(card).not.toContainText(label(L, 'sample.liveReading'))
  // Nothing ran, so nothing is polled.
  expect(mocks.requests.filter((r) => r.method === 'GET' && r.path.startsWith('/reports/'))).toHaveLength(0)
})

test('a 503 uploads_paused on a sample run shows the paused line, never an error', async ({ page, mocks }) => {
  mocks.behaviour.sampleRun = 'paused'
  await page.goto('/#/tested')
  const item = page.getByRole('listitem').filter({ hasText: FIRST.credit })
  await item.getByRole('button', { name: label(L, 'sample.run'), exact: true }).click()
  await acceptAdult(page, L)
  await expect(item).toContainText(label(L, 'result.paused'))
  await expect(item).not.toContainText(label(L, 'result.failed'))
  await expect(item).not.toContainText(label(L, 'report.nothingUploaded'))
})

test('a sample run that refuses shows the can\'t-tell card in the sample frame, never an error', async ({ page, mocks }) => {
  mocks.behaviour.sampleOutcome = { kind: 'refused', reason: 'no_usable_reference' }
  await page.goto('/#/tested')
  const item = page.getByRole('listitem').filter({ hasText: FIRST.credit })
  await item.getByRole('button', { name: label(L, 'sample.run'), exact: true }).click()
  await acceptAdult(page, L)
  const card = item.locator('article[data-outcome="cant-tell"]')
  await expect(card).toBeVisible()
  // C637: it doesn't ask the judge to retake a photo they didn't take; D19's line sits in its frame.
  await expect(card).toContainText(label(L, 'refusal.sample.cantTell'))
  await expect(card).toContainText(label(L, 'reason.no_usable_reference'))
  await expect(card).toContainText(label(L, 'refusal.sample.someoneWouldSee'))
  await expect(card).toContainText(label(L, 'refusal.d19'))
  await expect(card).toContainText(FIRST.credit)
  await expect(card.getByRole('img', { name: label(L, 'sample.photoAlt') })).toBeVisible()
})

for (const [name, count] of [
  ['an empty list', 0],
  ['a list of one', 1],
  ['a failed list', 'error'],
] as const) {
  test(`a short samples list still reads well: ${name}`, async ({ page, mocks }) => {
    mocks.behaviour.sampleCount = count
    await page.goto('/#/tested')
    const main = page.getByRole('main')
    await expect(main).toContainText(label(L, 'tested.samples.more'))
    await expect(page.getByRole('button', { name: label(L, 'sample.run'), exact: true })).toHaveCount(count === 1 ? 1 : 0)
    // The page keeps its other sections, and shows no error.
    await expect(page.getByRole('heading', { name: label(L, 'tested.how.title') })).toBeVisible()
    await expect(page.getByRole('heading', { name: label(L, 'tested.limits.title') })).toBeVisible()
    await expect(main).toContainText(label(L, 'tested.pending'))
    await expect(main).not.toContainText(label(L, 'sample.failed'))
    await expect(page.getByRole('alert')).toHaveCount(0)
  })
}
