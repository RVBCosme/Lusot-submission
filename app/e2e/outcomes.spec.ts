// One test per outcome of spec §4.2, from the fake camera to the result card (MS5 Task 18, U5): no flood seen, can't
// tell, processing failed, the pause twice (a report ending failed/model_calls_paused, and a 503 uploads_paused on the
// upload, C638), a photo taken outside Metro Manila, and the app's own "No result yet" (C601). The level row is
// report.spec.ts. The `dark` project plays a night scene as the camera and runs only the quality-check test here.
import { expect, OWN_ID, test, type Mocks } from './mocks'
import { expectResult, label, send, takePhoto, toPlaceStep } from './steps'

const L = 'en'
const uploads = (mocks: Mocks) => mocks.requests.filter((r) => r.method === 'POST' && r.path === '/uploads').length
const reads = (mocks: Mocks) => mocks.requests.filter((r) => r.method === 'GET' && r.path === `/reports/${OWN_ID}`).length
const FAILED = new RegExp(label(L, 'result.failed').replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))

test('no flood seen: its own line, an empty gauge, and no pin of the person\'s own', async ({ page, mocks }) => {
  mocks.behaviour.outcome = { kind: 'no_flood' }
  mocks.behaviour.pins = []
  await toPlaceStep(page, L)
  await send(page, L)
  await expectResult(page, L, 'no-flood')
  const card = page.locator('article[data-outcome="no-flood"]')
  await expect(card).toContainText(label(L, 'result.noFlood'))
  await expect(card).not.toContainText(FAILED)
  // "No flood seen" isn't published (MS4's C506), so the map holds no pin of the person's own.
  await page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.map'), exact: true }).click()
  await expect(page.getByRole('heading', { name: label(L, 'map.empty.title') })).toBeVisible()
  await expect(page.getByRole('button', { name: new RegExp(`^${label(L, 'map.own')}\\.`) })).toHaveCount(0)
})

test('can\'t tell: D19\'s line, then the plain reason line, and a new photo on offer', async ({ page, mocks }) => {
  mocks.behaviour.outcome = { kind: 'refused', reason: 'no_usable_reference' }
  await toPlaceStep(page, L)
  await send(page, L)
  await expectResult(page, L, 'cant-tell')
  const card = page.locator('article[data-outcome="cant-tell"]')
  await expect(card).toContainText(label(L, 'refusal.d19'))
  await expect(card).toContainText(label(L, 'reason.no_usable_reference'))
  await expect(card).not.toContainText(FAILED)
  await page.getByRole('button', { name: label(L, 'report.newPhoto'), exact: true }).click()
  await expect(page.getByRole('button', { name: label(L, 'camera.shutter'), exact: true })).toBeVisible()
  expect(uploads(mocks), 'a new photo is not a resend').toBe(1)
})

test('processing failed: its own line and reason, and "Try again" starts a new photo, never a resend', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.outcome = { kind: 'failed', reason: 'pipeline_error' }
  await toPlaceStep(page, L)
  await send(page, L)
  await expectResult(page, L, 'failed')
  const card = page.locator('article[data-outcome="failed"]')
  await expect(card).toContainText(label(L, 'result.failed'))
  await expect(card).toContainText(label(L, 'reason.pipeline_error'))
  await card.getByRole('button', { name: label(L, 'result.tryAgain'), exact: true }).click()
  await expect(page.getByRole('heading', { name: label(L, 'camera.title') })).toBeVisible()
  expect(uploads(mocks), 'the failed photo was not sent again').toBe(1)
})

test('paused during the analysis: the paused line, never "Processing failed", with links and no retry', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.outcome = { kind: 'failed', reason: 'model_calls_paused' }
  await toPlaceStep(page, L)
  await send(page, L)
  await expectResult(page, L, 'paused')
  const card = page.locator('article[data-outcome="paused"]')
  await expect(card).toContainText(label(L, 'result.paused'))
  await expect(card).not.toContainText(FAILED)
  // C638: no reason line and no "Try again", since a new photo would pause the same way; links to the map and Tested.
  // The reason's own line begins the paused line, so the paused words show once, with no reason line after them.
  const pausedWords = label(L, 'reason.model_calls_paused')
  expect((await card.innerText()).split(pausedWords).length - 1, 'the paused words show once').toBe(1)
  await expect(page.getByRole('button', { name: label(L, 'result.tryAgain'), exact: true })).toHaveCount(0)
  await expect(card.getByRole('link', { name: label(L, 'nav.map'), exact: true })).toBeVisible()
  await expect(card.getByRole('link', { name: label(L, 'nav.tested'), exact: true })).toBeVisible()
})

test('paused before the upload: the paused line and "Nothing was uploaded.", and "Try again" reuses the photo', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.upload = 'paused'
  await toPlaceStep(page, L)
  await send(page, L)
  await expect(page.getByRole('heading', { name: label(L, 'report.notSent') })).toBeVisible()
  const main = page.getByRole('main')
  await expect(main).toContainText(label(L, 'result.paused'))
  await expect(main).toContainText(label(L, 'report.nothingUploaded'))
  await expect(main).not.toContainText(FAILED)
  expect(mocks.requests.some((r) => r.path === `/uploads/${OWN_ID}`), 'nothing reached S3').toBe(false)

  // The switch comes back off: the same photo goes, with no new shutter press.
  mocks.behaviour.upload = 'ok'
  await page.getByRole('button', { name: label(L, 'result.tryAgain'), exact: true }).click()
  await expectResult(page, L, 'level')
  expect(uploads(mocks)).toBe(2)
  expect(mocks.requests.filter((r) => r.path === `/uploads/${OWN_ID}`)).toHaveLength(1)
})

test('outside Metro Manila: the result with the private line, and no pin of the person\'s own', async ({ page, mocks }) => {
  mocks.behaviour.mode = 'private'
  mocks.behaviour.pins = []
  await toPlaceStep(page, L)
  await send(page, L)
  await expectResult(page, L, 'level')
  const card = page.locator('article[data-outcome="level"]')
  await expect(card).toContainText(new RegExp(`${label(L, 'result.levelName.knee')} deep at this spot`, 'i'))
  await expect(page.getByRole('main')).toContainText(label(L, 'result.private'))
  await page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.map'), exact: true }).click()
  await expect(page.getByRole('heading', { name: label(L, 'map.empty.title') })).toBeVisible()
  await expect(page.getByRole('button', { name: new RegExp(`^${label(L, 'map.own')}\\.`) })).toHaveCount(0)
})

test('no result after 10 minutes: "No result yet", never a failure, and "Check again" reads the same report', async ({
  page,
  mocks,
}) => {
  // The app's clock is under the test's control; it runs on at its own pace until the test jumps it forward.
  await page.clock.install()
  mocks.behaviour.pendingReads = Number.POSITIVE_INFINITY
  await toPlaceStep(page, L)
  await send(page, L)
  await expect(page.getByRole('heading', { name: label(L, 'report.waitingTitle') })).toBeVisible()
  await expect.poll(() => reads(mocks)).toBeGreaterThan(0)

  // Past the 600 s window (C601), in steps the poll's own timers can follow.
  for (let i = 0; i < 12; i += 1) await page.clock.fastForward('01:00')
  const card = page.locator('article[data-outcome="no-result"]')
  await expect(card).toBeVisible()
  await expect(card).toContainText(label(L, 'result.noResult'))
  await expect(page.getByRole('main')).not.toContainText(FAILED)

  // "Check again" polls the same report and never uploads again; this time the result is there.
  mocks.behaviour.pendingReads = 0
  const before = reads(mocks)
  await card.getByRole('button', { name: label(L, 'result.checkAgain'), exact: true }).click()
  await expect.poll(() => reads(mocks)).toBeGreaterThan(before)
  await expectResult(page, L, 'level')
  expect(uploads(mocks), 'no second upload').toBe(1)
})

test('a dark photo: the quality check', async ({ page, mocks }) => {
  // The night scene is what the camera gives: its mean grey value is under the server's too_dark cutoff of 40.
  mocks.behaviour.outcome = { kind: 'refused', reason: 'too_dark' }
  await page.goto('/#/report')
  await page.getByRole('checkbox', { name: label(L, 'consent.adult') }).check()
  await page.getByRole('button', { name: label(L, 'consent.continue'), exact: true }).click()
  await expect(page.getByRole('button', { name: label(L, 'camera.shutter'), exact: true })).toBeEnabled()
  const brightness = await page.locator('video').evaluate((video: HTMLVideoElement) => {
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')!
    context.drawImage(video, 0, 0)
    const { data } = context.getImageData(0, 0, canvas.width, canvas.height)
    let sum = 0
    for (let i = 0; i < data.length; i += 4) sum += (data[i]! * 4899 + data[i + 1]! * 9617 + data[i + 2]! * 1868 + 8192) >> 14
    return sum / (data.length / 4)
  })
  expect(brightness, 'the dark camera is too dark to read').toBeLessThan(40)
  await takePhoto(page, L)
  // Without a phone-side check the photo goes on, and the server's own check refuses it (C604: the server checks again).
  await expect(page.getByRole('heading', { name: label(L, 'place.title') })).toBeVisible()
  await send(page, L)
  await expectResult(page, L, 'cant-tell')
  await expect(page.locator('article[data-outcome="cant-tell"]')).toContainText(label(L, 'reason.too_dark'))
})
