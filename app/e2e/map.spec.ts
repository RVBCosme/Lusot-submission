// The map (MS5 Task 18, C612, C613, C618, U6): live and demo pins, the list of the same pins newest first, pin detail
// with its photo, the flag on live pins only, and the empty state. Every answer is a route in mocks.ts; the pins are the
// mock's own (src/mock/fixtures.ts): live pins 10, 25 and 90 minutes old, one past 3 hours that the map hides, a demo
// pin from 2009, and one with a level outside the 9, which the app drops.
import { pinSpecs } from '../src/mock/fixtures'
import { DEMO_PIN, expect, LIVE_PIN, test } from './mocks'
import { label } from './steps'

const L = 'en'
const deep = (key: 'knee' | 'half_tire' | 'tire' | 'above_chest') => new RegExp(`${label(L, `result.levelName.${key}`)} deep at this spot`, 'i')

test('live and demo pins on the map and in the list, newest first, each opening its pin detail', async ({ page, mocks }) => {
  mocks.behaviour.pins = pinSpecs()
  await page.goto('/#/map')
  // Four pins show: the three live ones under 3 hours and the demo pin. The one past 3 hours and the unwordable one don't.
  await expect(page.locator('.map-pin')).toHaveCount(4)
  await expect(page.getByRole('button', { name: new RegExp(`^${label(L, 'badge.demo')}\\.`) })).toHaveCount(1)
  // The OpenStreetMap credit links to its copyright page.
  await expect(page.locator('.leaflet-control-attribution a[href="https://www.openstreetmap.org/copyright"]')).toHaveText(
    '© OpenStreetMap contributors',
  )

  await page.getByRole('button', { name: label(L, 'map.list'), exact: true }).click()
  const rows = page.getByRole('list', { name: label(L, 'map.listLabel') }).getByRole('listitem')
  await expect(rows).toHaveCount(4)
  await expect(rows.nth(0)).toContainText(deep('knee'))
  await expect(rows.nth(1)).toContainText(deep('half_tire'))
  await expect(rows.nth(2)).toContainText(deep('tire'))
  await expect(rows.nth(3)).toContainText(deep('above_chest'))
  await expect(rows.nth(3)).toContainText(label(L, 'badge.demo'))

  // The newest row opens its pin detail, with the result card and its photo.
  await rows.nth(0).getByRole('link').click()
  await expect(page).toHaveURL(new RegExp(`#/pin/${LIVE_PIN.id}$`))
  const card = page.locator('article[data-outcome="level"]')
  await expect(card).toContainText(deep('knee'))
  const photo = card.locator('img').first()
  await expect(photo).toBeVisible()
  await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  // The other live pin 70 m away is counted as nearby (within 300 m and 3 hours).
  await expect(page.getByRole('main')).toContainText(label(L, 'pin.nearby', { count: 1 }))
})

test('a live pin can be flagged once, after a confirmation; a demo pin has no flag button', async ({ page, mocks }) => {
  mocks.behaviour.pins = [LIVE_PIN, DEMO_PIN]
  await page.goto(`/#/pin/${LIVE_PIN.id}`)
  await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
  const flags = () => mocks.requests.filter((r) => r.method === 'POST' && r.path.endsWith('/flag'))

  // It asks first; "Cancel" sends nothing.
  await page.getByRole('button', { name: label(L, 'pin.flag'), exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText(label(L, 'flag.title'))
  await dialog.getByRole('button', { name: label(L, 'flag.cancel'), exact: true }).click()
  await expect(dialog).toBeHidden()
  expect(flags()).toHaveLength(0)

  await page.getByRole('button', { name: label(L, 'pin.flag'), exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: label(L, 'flag.confirm'), exact: true }).click()
  await expect(page.getByRole('main')).toContainText(label(L, 'pin.flagged'))
  await expect(page.getByRole('main')).toContainText(label(L, 'pin.flags.one', { count: 1 }))
  // "Flagged" for the rest of the visit: no second flag on offer.
  await expect(page.getByRole('button', { name: label(L, 'pin.flag'), exact: true })).toHaveCount(0)
  expect(flags()).toHaveLength(1)
  expect(flags()[0]!.headers['x-lusot-device']).not.toBe('')

  // The demo pin: its badge, its photo's date, place and event, its credit, and no flag button (N12).
  await page.goto(`/#/pin/${DEMO_PIN.id}`)
  const demo = page.locator('article[data-outcome="level"]')
  await expect(demo).toContainText(deep('above_chest'))
  await expect(demo).toContainText(label(L, 'badge.demo'))
  await expect(demo).toContainText(DEMO_PIN.demo!.place)
  await expect(demo).toContainText(DEMO_PIN.demo!.event)
  await expect(demo).toContainText('2009')
  await expect(demo).toContainText(DEMO_PIN.demo!.credit)
  await expect(page.getByRole('button', { name: label(L, 'pin.flag'), exact: true })).toHaveCount(0)
})

test('a pin no longer on the map says so, with no card', async ({ page, mocks }) => {
  mocks.behaviour.pins = []
  await page.goto(`/#/pin/${LIVE_PIN.id}`)
  await expect(page.getByRole('main')).toContainText(label(L, 'pin.gone'))
  await expect(page.locator('article[data-outcome]')).toHaveCount(0)
})

test('an empty map: "No reports in the last 3 hours", "Try a sample", and one card marked as an example', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.pins = []
  await page.goto('/#/map')
  await expect(page.getByRole('heading', { name: label(L, 'map.empty.title') })).toBeVisible()
  await expect(page.locator('.map-pin')).toHaveCount(0)
  // One example card, marked as an example, and no reading card that could pass for a real one.
  await expect(page.locator('article').filter({ hasText: label(L, 'badge.example') })).toHaveCount(1)
  await expect(page.locator('article[data-outcome]')).toHaveCount(0)
  await page.getByRole('link', { name: label(L, 'map.trySample'), exact: true }).click()
  await expect(page).toHaveURL(/#\/tested$/)
  await expect(page.getByRole('heading', { name: label(L, 'nav.tested'), level: 1 })).toBeVisible()
})
