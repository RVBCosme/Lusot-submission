// Accessibility (MS5 Task 18, C625, U9): axe on every route and every step of the report flow, in both themes, with no
// serious or critical finding; every button and link in the navigation, the report flow and the result card at least
// 48 x 48 px; and with the root font size at 200%, no sideways scroll on the map, report, result and Tested screens.
import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import { expect, LIVE_PIN, test } from './mocks'
import { acceptNotice, choose, label, send, takePhoto } from './steps'

const L = 'en'
const TAP = 48

async function expectNoSeriousFinding(page: Page, where: string): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
  const serious = violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.map((node) => node.target.join(' ')).join(' | ')}`)
  expect.soft(serious, `${where}: serious or critical axe findings`).toEqual([])
}

// Every button and link inside `scope` that is drawn, with its size, smaller than 48 x 48 px. The map's own Leaflet
// controls are out of scope here: their zoom buttons are the app's own (map.zoomIn, map.zoomOut), and the
// OpenStreetMap credit is a line of text the tile policy asks for.
async function smallTargets(page: Page, scope: string): Promise<string[]> {
  return page.evaluate(
    ({ scope, tap }) => {
      const small: string[] = []
      for (const root of document.querySelectorAll(scope)) {
        for (const el of root.querySelectorAll<HTMLElement>('a[href], button')) {
          if (el.closest('.leaflet-control-attribution') !== null) continue
          const box = el.getBoundingClientRect()
          if (box.width === 0 && box.height === 0) continue
          if (box.width + 0.5 < tap || box.height + 0.5 < tap) {
            const name = (el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 40)
            small.push(`${el.tagName.toLowerCase()} "${name}" ${Math.round(box.width)} x ${Math.round(box.height)}`)
          }
        }
      }
      return small
    },
    { scope, tap: TAP },
  )
}

// The page and the screen's own scrolling <main>, which would hide a too-wide screen from the page's own measure.
async function noSidewaysScroll(page: Page, where: string): Promise<void> {
  const overflow = await page.evaluate(() =>
    [document.documentElement, document.querySelector('main')].map((el) => (el === null ? 0 : el.scrollWidth - el.clientWidth)),
  )
  expect.soft(overflow, `${where}: sideways scroll at 200% text, the page and <main>`).toEqual([0, 0])
}

for (const theme of ['light', 'dark'] as const) {
  test(`axe finds nothing serious on any route or report step, ${theme} theme`, async ({ page }) => {
    await choose(page, { theme })
    const at = (where: string) => `${theme}, ${where}`
    await page.goto('/#/map')
    await expect(page.locator('.map-pin').first()).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    await expectNoSeriousFinding(page, at('#/map'))
    await page.getByRole('button', { name: label(L, 'map.list'), exact: true }).click()
    await expectNoSeriousFinding(page, at('#/map, the list'))
    await page.goto(`/#/pin/${LIVE_PIN.id}`)
    await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
    await expectNoSeriousFinding(page, at('#/pin/<id>'))
    for (const [route, key] of [
      ['/#/tested', 'nav.tested'],
      ['/#/about', 'nav.about'],
      ['/#/privacy', 'privacy.title'],
      ['/#/licences', 'licences.title'],
      ['/#/ask', 'nav.ask'],
    ] as const) {
      await page.goto(route)
      await expect(page.getByRole('heading', { name: label(L, key), level: 1 })).toBeVisible()
      await expect(page.getByText(label(L, 'licences.loading'))).toBeHidden()
      await expect(page.getByText(label(L, 'tested.samples.loading'))).toBeHidden()
      await expectNoSeriousFinding(page, at(route))
    }
    await page.goto('/#/report')
    await expect(page.getByTestId('notice')).toBeVisible()
    await expectNoSeriousFinding(page, at('#/report, the notice'))
    await acceptNotice(page, L)
    await expect(page.getByRole('button', { name: label(L, 'camera.shutter'), exact: true })).toBeEnabled()
    await expectNoSeriousFinding(page, at('#/report, the camera'))
    await takePhoto(page, L)
    await expect(page.getByRole('heading', { name: label(L, 'place.title') })).toBeVisible()
    await expectNoSeriousFinding(page, at('#/report, the place step'))
    await send(page, L)
    await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
    await expectNoSeriousFinding(page, at('#/report, the result'))
  })
}

test('every button and link in the navigation, the report flow and the result card is at least 48 x 48 px', async ({
  page,
  mocks,
}) => {
  const check = async (where: string, scope: string) => expect.soft(await smallTargets(page, scope), where).toEqual([])
  await page.goto('/#/map')
  await expect(page.locator('.map-pin').first()).toBeVisible()
  await check('the navigation and the header', 'nav, header')
  await page.goto(`/#/pin/${LIVE_PIN.id}`)
  await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
  await check('a pin\'s result card', 'article[data-outcome]')
  await page.goto('/#/report')
  await check('#/report, the notice', 'main')
  await acceptNotice(page, L)
  await expect(page.getByRole('button', { name: label(L, 'camera.shutter'), exact: true })).toBeEnabled()
  await check('#/report, the camera', 'main')
  await takePhoto(page, L)
  await expect(page.getByRole('heading', { name: label(L, 'place.title') })).toBeVisible()
  await check('#/report, the place step', 'main')
  await send(page, L)
  await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
  await check('#/report, the result', 'main')
  // A paused card, whose links are the short "Map" and "Tested".
  mocks.behaviour.outcome = { kind: 'failed', reason: 'model_calls_paused' }
  await page.getByRole('button', { name: label(L, 'report.newPhoto'), exact: true }).click()
  await takePhoto(page, L)
  await send(page, L)
  await expect(page.locator('article[data-outcome="paused"]')).toBeVisible()
  await check('#/report, a paused result', 'main')
})

test('with the root font size at 200%, the map, report, result and Tested screens have no sideways scroll', async ({
  page,
}) => {
  await page.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      document.documentElement.style.fontSize = '200%'
    })
  })
  await page.goto('/#/map')
  await expect(page.locator('.map-pin').first()).toBeVisible()
  await noSidewaysScroll(page, '#/map')
  await page.getByRole('button', { name: label(L, 'map.list'), exact: true }).click()
  await noSidewaysScroll(page, '#/map, the list')
  await page.goto('/#/tested')
  await expect(page.getByRole('button', { name: label(L, 'sample.run'), exact: true }).first()).toBeVisible()
  await noSidewaysScroll(page, '#/tested')
  await page.goto('/#/report')
  await expect(page.getByTestId('notice')).toBeVisible()
  await noSidewaysScroll(page, '#/report, the notice')
  await acceptNotice(page, L)
  await expect(page.getByRole('button', { name: label(L, 'camera.shutter'), exact: true })).toBeEnabled()
  await noSidewaysScroll(page, '#/report, the camera')
  await takePhoto(page, L)
  await expect(page.getByRole('heading', { name: label(L, 'place.title') })).toBeVisible()
  await noSidewaysScroll(page, '#/report, the place step')
  await send(page, L)
  await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
  await noSidewaysScroll(page, '#/report, the result')
  // The root really is at 200%.
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe('32px')
})
