// The desktop layout, at 1280 x 800 (from lg, 64 rem). One nav, drawn in a top bar with the brand and the language switch, and
// no bar of tabs at the bottom (the page holds the nav twice, and each width displays one copy); the keyboard following the
// bar in the order it is drawn; the screen line pinned along the bottom, once; the map across the whole window, with the list
// in a panel of 24 rem beside it; a level result card in two columns, the photo on the left; the Tested samples in two columns,
// the sections of reading kept to a line of 65 characters; and axe on the map, a report's result, Tested and About. Below lg
// nothing changes: every other spec runs at 360 or 390 px and says so. Every answer is a route in mocks.ts.
import AxeBuilder from '@axe-core/playwright'
import type { Locator, Page } from '@playwright/test'
import { pinSpecs } from '../src/mock/fixtures'
import { expect, LIVE_PIN, test } from './mocks'
import { expectLine, LINE } from './screenLine'
import { acceptNotice, choose, label, send, takePhoto } from './steps'

const L = 'en'
const WIDTH = 1280
const HEIGHT = 800
// 24 rem, the width of the list's panel beside the map.
const PANEL = 384

// The viewport is the desktop's. The entrance of the result card and the samples (index.css's .rise-in) doesn't run for a person
// who asked for less motion, and axe would read a card half faded in as text with half its contrast, so the spec asks for that.
test.use({ viewport: { width: WIDTH, height: HEIGHT }, reducedMotion: 'reduce' })

type Box = { x: number; y: number; width: number; height: number }

// Where a locator is drawn, in the viewport.
async function box(locator: Locator): Promise<Box> {
  await expect(locator).toBeVisible()
  const drawn = await locator.boundingBox()
  expect(drawn, 'the element is drawn').not.toBeNull()
  return drawn as Box
}

const bottom = (b: Box) => b.y + b.height
const right = (b: Box) => b.x + b.width

async function expectNoSeriousFinding(page: Page, where: string): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
  const serious = violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((node) => node.target.join(' ')).join(' | ')}`)
  expect.soft(serious, `${where}: serious or critical axe findings`).toEqual([])
}

test('one nav, in a top bar between the brand and the language switch; the screen line stays along the bottom, once', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.pins = [LIVE_PIN]
  await page.goto('/#/map')
  await expect(page.locator('.map-pin').first()).toBeVisible()

  // One navigation landmark, whatever the width: the header's copy is displayed and the footer's (the phone's bar of tabs)
  // is `display: none`, so it is out of the accessibility tree as well as out of sight.
  const nav = page.getByRole('navigation')
  await expect(nav).toHaveCount(1)
  await expect(page.locator('header nav')).toBeVisible()
  await expect(page.locator('footer nav')).toBeHidden()
  const links = nav.getByRole('link')
  await expect(links).toHaveText([
    label(L, 'nav.map'),
    label(L, 'nav.report'),
    label(L, 'nav.tested'),
    label(L, 'nav.about'),
    label(L, 'nav.ask'),
  ])
  const navBox = await box(nav)
  const mainBox = await box(page.getByRole('main'))
  const brandBox = await box(page.getByRole('banner').getByText('Lusot', { exact: true }))
  const switchBox = await box(page.getByRole('group', { name: label(L, 'lang.switch') }))
  // The bar is above the screen, with nothing of the nav below it.
  expect(bottom(navBox)).toBeLessThanOrEqual(mainBox.y + 1)
  expect(bottom(brandBox)).toBeLessThanOrEqual(mainBox.y + 1)
  expect(bottom(switchBox)).toBeLessThanOrEqual(mainBox.y + 1)
  expect(navBox.y).toBeLessThan(HEIGHT / 8)
  // Left to right: the brand, the nav, the language switch.
  expect(right(brandBox)).toBeLessThanOrEqual(navBox.x + 1)
  expect(right(navBox)).toBeLessThanOrEqual(switchBox.x + 1)
  // The five links share one row, each a target of at least 48 x 48 px, an icon beside its label.
  const tops = await links.evaluateAll((all) => all.map((link) => Math.round(link.getBoundingClientRect().top)))
  expect(new Set(tops).size).toBe(1)
  for (const link of await links.all()) {
    const linkBox = await box(link)
    expect.soft(linkBox.width, 'a link is at least 48 px wide').toBeGreaterThanOrEqual(47.5)
    expect.soft(linkBox.height, 'a link is at least 48 px tall').toBeGreaterThanOrEqual(47.5)
    expect.soft(await link.locator('svg').count(), 'a link has its icon').toBe(1)
  }
  // The section the screen belongs to is marked as it is on a phone: aria-current, and an underline.
  await expect(links.first()).toHaveAttribute('aria-current', 'page')
  await expect(links.nth(1)).not.toHaveAttribute('aria-current')
  expect(await links.first().evaluate((link) => getComputedStyle(link).textDecorationLine)).toContain('underline')
  expect(await links.nth(1).evaluate((link) => getComputedStyle(link).textDecorationLine)).not.toContain('underline')

  // The screen line is along the bottom, the window's whole width, below the screen, and on every screen once.
  const line = await box(page.getByText(LINE, { exact: true }))
  expect(line.y).toBeGreaterThanOrEqual(bottom(mainBox) - 1)
  expect(bottom(line)).toBeLessThanOrEqual(HEIGHT + 0.5)
  expect(line.width).toBeGreaterThanOrEqual(WIDTH - 2)
  const at = (where: string) => `${WIDTH} x ${HEIGHT}, ${where}`
  await expectLine(page, at('#/map'))
  for (const [route, key] of [
    ['/#/tested', 'nav.tested'],
    ['/#/about', 'nav.about'],
    ['/#/ask', 'nav.ask'],
  ] as const) {
    await page.goto(route)
    await expect(page.getByRole('heading', { name: label(L, key), level: 1 })).toBeVisible()
    await expectLine(page, at(route))
    await expect(page.getByRole('navigation')).toHaveCount(1)
  }
  await page.goto(`/#/pin/${LIVE_PIN.id}`)
  await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
  await expectLine(page, at('#/pin/<id>'))
})

test('the keyboard follows the bar as it is drawn: the five links, the language switch, then the screen, and no nav after it', async ({
  page,
}) => {
  await page.goto('/#/privacy')
  await expect(page.getByRole('heading', { name: label(L, 'privacy.title'), level: 1 })).toBeVisible()
  // Each Tab stop, named by where it is: a nav link by its text, the language switch, the screen, or the page's own end.
  const seen: string[] = []
  for (let press = 0; press < 25; press++) {
    await page.keyboard.press('Tab')
    const where = await page.evaluate(() => {
      const focused = document.activeElement
      if (focused === null || focused === document.body) return 'END'
      if (focused.closest('nav') !== null) return `nav: ${(focused.textContent ?? '').trim()}`
      if (focused.closest('header') !== null) return 'language switch'
      if (focused.closest('main') !== null) return 'screen'
      return `other: ${focused.tagName}`
    })
    // The screen may hold links of its own, which count as one stop here; a stop seen twice means the Tab order wrapped round.
    if (where === 'END' || (where !== seen.at(-1) && seen.includes(where))) break
    if (where !== seen.at(-1)) seen.push(where)
  }
  expect(seen).toEqual([
    ...(['nav.map', 'nav.report', 'nav.tested', 'nav.about', 'nav.ask'] as const).map((key) => `nav: ${label(L, key)}`),
    'language switch',
    'screen',
  ])
})

test('the map runs across the whole window; the list opens in a panel of 24 rem beside it, and the map stays', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.pins = pinSpecs()
  await page.goto('/#/map')
  await expect(page.locator('.map-pin')).toHaveCount(4)

  const map = page.locator('.leaflet-container')
  const wholeMap = await box(map)
  const navBox = await box(page.getByRole('navigation'))
  const lineBox = await box(page.getByText(LINE, { exact: true }))
  // At least 90% of the window's width, in fact edge to edge; under the bar and above the line, and tall.
  expect(wholeMap.width).toBeGreaterThanOrEqual(WIDTH * 0.9)
  expect(wholeMap.x).toBeLessThanOrEqual(1)
  expect(right(wholeMap)).toBeGreaterThanOrEqual(WIDTH - 1)
  expect(wholeMap.y).toBeGreaterThanOrEqual(bottom(navBox) - 1)
  expect(bottom(wholeMap)).toBeLessThanOrEqual(lineBox.y + 1)
  expect(wholeMap.height).toBeGreaterThan(HEIGHT * 0.55)
  // The OpenStreetMap credit is drawn on the map, above the screen line.
  const credit = await box(page.locator('.leaflet-control-attribution a[href="https://www.openstreetmap.org/copyright"]'))
  expect(bottom(credit)).toBeLessThanOrEqual(lineBox.y + 0.5)

  await page.getByRole('button', { name: label(L, 'map.list'), exact: true }).click()
  const list = page.getByRole('list', { name: label(L, 'map.listLabel') })
  await expect(list).toBeVisible()
  // The map stays, with its markers, narrower by the panel; the panel is 24 rem wide and on the right.
  await expect(page.locator('.map-pin')).toHaveCount(4)
  const beside = await box(map)
  // The panel is two boxes up from the list: the box that scrolls the list, inside the panel and its edge.
  const panel = await list.evaluate((ul) => {
    const drawn = ((ul.parentElement as HTMLElement).parentElement as HTMLElement).getBoundingClientRect()
    return { x: drawn.x, width: drawn.width, right: drawn.right }
  })
  expect(panel.width).toBeCloseTo(PANEL, 0)
  expect(panel.right).toBeGreaterThanOrEqual(WIDTH - 1)
  expect(Math.abs(right(beside) - panel.x)).toBeLessThanOrEqual(1.5)
  expect(Math.abs(beside.width - (WIDTH - PANEL))).toBeLessThanOrEqual(2)
  // The rows are all there and a row is a link to its pin.
  await expect(list.getByRole('listitem')).toHaveCount(4)
  const listBox = await box(list)
  expect(listBox.x).toBeGreaterThanOrEqual(right(beside) - 1)
  expect(right(listBox)).toBeLessThanOrEqual(WIDTH + 0.5)
})

test('a level result card is in two columns: the photo on the left, the verdict, the level and the gauge on the right', async ({
  page,
  mocks,
}) => {
  mocks.behaviour.pins = [LIVE_PIN]
  await page.goto(`/#/pin/${LIVE_PIN.id}`)
  const card = page.locator('article[data-outcome="level"]')
  await expect(card).toBeVisible()
  const photo = card.locator('figure img').first()
  await expect(photo).toBeVisible()
  await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)

  const figure = await box(card.locator('figure'))
  const photoBox = await box(photo)
  const reading = await box(card.getByRole('status').first().locator('xpath=..'))
  const verdict = await box(card.locator('[data-level-line]'))
  const gauge = await box(card.getByTestId('gauge'))
  // The photo's box is left of the verdict line's, and so is the gauge to its right, the two columns side by side on one row.
  expect(right(photoBox)).toBeLessThanOrEqual(verdict.x + 1)
  expect(gauge.x).toBeGreaterThanOrEqual(right(photoBox) - 1)
  expect(Math.abs(figure.y - reading.y)).toBeLessThanOrEqual(2)
  // About 55% for the photo's column.
  expect(figure.width / (figure.width + reading.width)).toBeCloseTo(0.55, 1)
  // The lines under the two columns run across both: the official links start at the card's left edge.
  const cardBox = await box(card)
  const sites = await box(card.getByRole('list', { name: label(L, 'about.officialTitle') }))
  expect(sites.x).toBeLessThan(cardBox.x + 40)
  expect(sites.y).toBeGreaterThanOrEqual(Math.max(bottom(figure), bottom(reading)) - 1)
})

test('the Tested samples sit two by two, and the sections of reading keep to a line of 65 characters', async ({ page }) => {
  await page.goto('/#/tested')
  const run = page.getByRole('button', { name: label(L, 'sample.run'), exact: true })
  await expect(run.first()).toBeVisible()
  await expect(run).toHaveCount(3)
  const items = page.getByRole('listitem').filter({ has: run })
  await expect(items).toHaveCount(3)

  const [first, second, third] = [await box(items.nth(0)), await box(items.nth(1)), await box(items.nth(2))]
  // The first two share a row, side by side; the third starts the next row, under the first.
  expect(Math.abs(first.y - second.y)).toBeLessThanOrEqual(2)
  expect(second.x).toBeGreaterThanOrEqual(right(first) - 1)
  expect(third.y).toBeGreaterThan(first.y + 50)
  expect(Math.abs(third.x - first.x)).toBeLessThanOrEqual(2)
  expect(first.width).toBeGreaterThan(400)
  expect(right(second)).toBeLessThanOrEqual(WIDTH)

  // A section of reading is a line of about 65 characters (65ch, near 600 px), not the 72 rem the samples have.
  const how = await box(page.getByRole('heading', { name: label(L, 'tested.how.title') }).locator('xpath=..'))
  expect(how.width).toBeLessThanOrEqual(700)
  const samples = await box(page.getByRole('heading', { name: label(L, 'tested.samples.title') }).locator('xpath=..'))
  expect(samples.width).toBeGreaterThan(1000)
})

for (const theme of ['light', 'dark'] as const) {
  test(`axe finds nothing serious at ${WIDTH} x ${HEIGHT} on the map, Tested, About and a report's result, ${theme} theme`, async ({
    page,
  }) => {
    await choose(page, { theme })
    const at = (where: string) => `${theme}, ${WIDTH} x ${HEIGHT}, ${where}`
    await page.goto('/#/map')
    await expect(page.locator('.map-pin').first()).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    await expectNoSeriousFinding(page, at('#/map'))
    await page.getByRole('button', { name: label(L, 'map.list'), exact: true }).click()
    await expect(page.getByRole('list', { name: label(L, 'map.listLabel') })).toBeVisible()
    await expectNoSeriousFinding(page, at('#/map, the list beside the map'))

    await page.goto('/#/tested')
    await expect(page.getByRole('heading', { name: label(L, 'nav.tested'), level: 1 })).toBeVisible()
    await expect(page.getByText(label(L, 'tested.samples.loading'))).toBeHidden()
    await expect(page.getByRole('button', { name: label(L, 'sample.run'), exact: true }).first()).toBeVisible()
    await expectNoSeriousFinding(page, at('#/tested'))

    await page.goto('/#/about')
    await expect(page.getByRole('heading', { name: label(L, 'nav.about'), level: 1 })).toBeVisible()
    await expectNoSeriousFinding(page, at('#/about'))

    await page.goto('/#/report')
    await expect(page.getByTestId('notice')).toBeVisible()
    await acceptNotice(page, L)
    await expect(page.getByRole('button', { name: label(L, 'camera.shutter'), exact: true })).toBeEnabled()
    await takePhoto(page, L)
    await expect(page.getByRole('heading', { name: label(L, 'place.title') })).toBeVisible()
    await send(page, L)
    await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
    await expectNoSeriousFinding(page, at('#/report, the result'))
  })
}
