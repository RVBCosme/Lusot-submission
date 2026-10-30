// The one end-to-end path (MS5 Task 18): from the notice to the fake camera's still, the fix and the place step, "Send",
// the upload and the photo's POST to S3, the poll to a level result in `live` mode, the result card, then the map with
// the person's own pin, which opens the person's own result. Every answer is a route in mocks.ts.
import { expect, OWN_ID, test } from './mocks'
import { label, takePhoto } from './steps'

const L = 'en'
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/

test('a photo goes from the fake camera to a level result and onto the map as the person\'s own pin', async ({ page, mocks }) => {
  // The first read of the report says "processing"; the second, two seconds later, has the result.
  mocks.behaviour.pendingReads = 1
  // The map holds no pin of anyone else's, so the only pin is the person's own.
  mocks.behaviour.pins = []

  await test.step('a fresh visit to #/report meets the notice, with the screen behind it hidden', async () => {
    await page.goto('/#/report')
    await expect(page.getByTestId('notice')).toBeVisible()
    // The camera screen is not drawn behind the notice (S5-R10): neither its heading nor its shutter is visible.
    await expect(page.getByRole('heading', { name: label(L, 'camera.title') })).toBeHidden()
    await expect(page.getByRole('button', { name: label(L, 'camera.shutter') })).toBeHidden()
    // "Continue" stays off until the 18+ box is ticked.
    const next = page.getByRole('button', { name: label(L, 'consent.continue'), exact: true })
    await expect(next).toBeDisabled()
    await page.getByRole('checkbox', { name: label(L, 'consent.adult') }).check()
    await expect(next).toBeEnabled()
    await next.click()
    await expect(page.getByTestId('notice')).toBeHidden()
  })

  await test.step('the camera plays the fake picture and the shutter takes a still', async () => {
    await expect(page.getByRole('heading', { name: label(L, 'camera.title') })).toBeVisible()
    // The shutter stays disabled until the first frame has played.
    await expect(page.getByRole('button', { name: label(L, 'camera.shutter'), exact: true })).toBeEnabled()
    const { width, height } = await page.locator('video').evaluate((video: HTMLVideoElement) => ({
      width: video.videoWidth,
      height: video.videoHeight,
    }))
    expect(width, 'the fake video is landscape and not tiny').toBeGreaterThan(height)
    expect(Math.max(width, height)).toBeGreaterThanOrEqual(1600)
    await takePhoto(page, L)
  })

  await test.step('the place step shows the fix on the map, with its credit', async () => {
    await expect(page.getByRole('heading', { name: label(L, 'place.title') })).toBeVisible()
    await expect(page.locator('.leaflet-control-attribution')).toContainText('© OpenStreetMap contributors')
    await expect(page.getByRole('status').filter({ hasText: /moved/ })).toHaveCount(0)
    await page.getByRole('button', { name: label(L, 'place.send'), exact: true }).click()
  })

  await test.step('the photo is sent and read, and the result card shows a level in live mode', async () => {
    // The first read answers "processing", so the waiting step shows for the two seconds before the next read.
    await expect(page.getByRole('heading', { name: label(L, 'report.waitingTitle') })).toBeVisible()
    await expect(page.getByRole('heading', { name: label(L, 'report.resultTitle') })).toBeVisible()
    const card = page.locator('article[data-outcome="level"]')
    await expect(card).toContainText(new RegExp(`${label(L, 'result.levelName.knee')} deep at this spot`, 'i'))
    await expect(card).toContainText(label(L, 'result.class.nplv'))
    // The photo link resolved to a picture that decoded.
    const photo = card.locator('img').first()
    await expect(photo).toBeVisible()
    await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  })

  await test.step('the requests were the API\'s own: the upload, the S3 POST and the poll', async () => {
    const upload = mocks.requests.find((r) => r.method === 'POST' && r.path === '/uploads')
    expect(upload, 'POST /uploads was made').toBeDefined()
    expect(Object.keys(upload!.json as object).sort()).toEqual(['capturedAt', 'consentVersion', 'gpsAccuracyM', 'lat', 'lng', 'nudgeM'])
    const body = upload!.json as { lat: number; lng: number; gpsAccuracyM: number; capturedAt: string; nudgeM: number; consentVersion: string }
    expect(body.lat).toBeCloseTo(14.6123456, 5)
    expect(body.lng).toBeCloseTo(121.0456789, 5)
    expect(body.gpsAccuracyM, 'the fix is 50 m or better').toBe(10)
    expect(body.nudgeM, 'the pin was not moved').toBe(0)
    expect(Math.abs(Date.now() - Date.parse(body.capturedAt)), 'the photo is minutes old at most').toBeLessThan(5 * 60_000)
    expect(body.consentVersion).not.toBe('')
    expect(upload!.headers['x-lusot-device']).toMatch(UUID)
    // S3 wants the policy's fields as given, then the file last.
    const s3 = mocks.requests.find((r) => r.method === 'POST' && r.path === `/uploads/${OWN_ID}`)
    expect(s3?.formFields).toEqual(['Content-Type', 'key', 'policy', 'x-amz-signature', 'file'])
    const polls = mocks.requests.filter((r) => r.method === 'GET' && r.path === `/reports/${OWN_ID}`)
    expect(polls.length, 'the report was read until it had a result').toBeGreaterThanOrEqual(2)
  })

  await test.step('the map shows the person\'s own pin, and it opens the person\'s own result', async () => {
    await page.getByRole('navigation').getByRole('link', { name: label(L, 'nav.map'), exact: true }).click()
    // The API's list holds no pins yet, so the pin is the one kept from this session (spec §4.4).
    const pin = page.getByRole('button', { name: new RegExp(`^${label(L, 'map.own')}\\.`) })
    await expect(pin).toBeVisible()
    await pin.click()
    await expect(page.getByRole('heading', { name: label(L, 'map.own') })).toBeVisible()
    const card = page.locator('article[data-outcome="level"]')
    await expect(card).toContainText(new RegExp(`${label(L, 'result.levelName.knee')} deep at this spot`, 'i'))
    await page.getByRole('button', { name: label(L, 'map.back') }).click()
    await expect(pin).toBeVisible()
  })
})
