// The copy rules on what a person sees (MS5 Task 18, C608, U4): the visible text of every route and every outcome, in
// both languages, holds no "safe" or "ligtas" in any word, no crossing phrase, no report id, and no "MMDA's 9 levels";
// and every level line says "at this spot" (Taglish: "sa spot na ito"). The string-table test checks the tables; this
// checks what the screens put together. The licences page is checked too, but not the third-party licence texts inside
// it, which are never reworded (S5-R23, C608): a banned form found there is recorded as an annotation for the controller.
import { readFileSync } from 'node:fs'
import type { Page, TestInfo } from '@playwright/test'
import { pinSpecs } from '../src/mock/fixtures'
import { DEMO_PIN, expect, LIVE_PIN, test, type Mocks } from './mocks'
import { acceptAdult, acceptNotice, choose, label, send, takePhoto, type Lang } from './steps'

// The banned forms come from scripts/copy-rules.json's `fail` rules (MS7's C819), the one rule set that
// scripts/check_copy.mjs and the string-table test read too, so the screens are held to the same words.
type FailRule = { id: string; pattern: string; flags: string }
const RULES = JSON.parse(readFileSync(new URL('../../scripts/copy-rules.json', import.meta.url), 'utf8')) as {
  fail: FailRule[]
}
function failRule(id: string): RegExp {
  const found = RULES.fail.find((rule) => rule.id === id)
  if (found === undefined) throw new Error(`scripts/copy-rules.json has no fail rule ${id}`)
  // As check_copy.mjs refuses them: g or y would make a match start where the last one ended.
  if (/[gy]/.test(found.flags)) throw new Error(`fail rule ${id} has a g or y flag`)
  return new RegExp(found.pattern, found.flags)
}
const SAFE = failRule('banned-safe')
const LIGTAS = failRule('banned-ligtas')
if (SAFE.flags !== LIGTAS.flags) throw new Error('banned-safe and banned-ligtas have different flags')
const BANNED = new RegExp(`${SAFE.source}|${LIGTAS.source}`, SAFE.flags)
const CROSSING = failRule('crossing-phrase')
const REPORT_ID = /r_[0-9a-f]{32}/
const NINE = failRule('mmda-9-levels')
const AT_THIS_SPOT: Record<Lang, RegExp> = { en: /at this spot/, fil: /sa spot na ito/ }

// The page's visible text, and apart from it the licence texts on the licences page.
async function visibleText(page: Page): Promise<{ text: string; licences: string }> {
  return page.evaluate(() => {
    // A closed Details holds the reason code and the photo's time (C610), where no report id may show either.
    for (const details of document.querySelectorAll('details')) details.open = true
    const licences = [...document.querySelectorAll('pre')].map((pre) => pre.innerText).join('\n')
    let text = document.body.innerText
    for (const pre of document.querySelectorAll('pre')) text = text.replace(pre.innerText, '')
    // Accessible names a screen reader reads aloud count as visible words too.
    const named = [...document.querySelectorAll('[aria-label]')].map((el) => el.getAttribute('aria-label') ?? '')
    return { text: `${text}\n${named.join('\n')}`, licences }
  })
}

// Every level line on the page: the cards', the list rows' and the markers' names.
async function levelLines(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const lines: string[] = []
    for (const card of document.querySelectorAll('article[data-outcome="level"]')) {
      const line = card.querySelector('[role="status"] p.text-title')
      if (line !== null) lines.push(line.textContent ?? '')
    }
    for (const row of document.querySelectorAll('ul li [data-line].font-bold')) lines.push(row.textContent ?? '')
    for (const pin of document.querySelectorAll('.map-pin[aria-label]')) lines.push(pin.getAttribute('aria-label') ?? '')
    return lines
  })
}

async function expectClean(page: Page, lang: Lang, where: string, testInfo: TestInfo): Promise<void> {
  const { text, licences } = await visibleText(page)
  expect.soft(text.match(BANNED)?.[0], `${where}: a banned word`).toBeUndefined()
  expect.soft(text.match(CROSSING)?.[0], `${where}: a crossing phrase`).toBeUndefined()
  expect.soft(text.match(REPORT_ID)?.[0], `${where}: a report id shown as text`).toBeUndefined()
  expect.soft(text.match(NINE)?.[0], `${where}: the 9 levels called MMDA's`).toBeUndefined()
  for (const line of await levelLines(page)) {
    expect.soft(line, `${where}: a level line says where`).toMatch(AT_THIS_SPOT[lang])
  }
  const hits = [...new Set([...licences.matchAll(new RegExp(BANNED.source, 'gi'))].map((match) => match[0]))]
  if (hits.length > 0) testInfo.annotations.push({ type: 'licence text, for the controller', description: `${where}: ${hits.join(', ')}` })
}

// A fresh load of a route, so nothing the last visit held in memory (a run's card, a finished report) carries over.
async function fresh(page: Page, route: string): Promise<void> {
  await page.goto('about:blank')
  await page.goto(route)
}

// One report from the fake camera to its result, ending as `outcome`.
async function report(page: Page, mocks: Mocks, lang: Lang, setUp: (mocks: Mocks) => void, outcome: string): Promise<void> {
  setUp(mocks)
  await fresh(page, '/#/report')
  await expect(page.getByRole('button', { name: label(lang, 'camera.shutter'), exact: true })).toBeEnabled()
  await takePhoto(page, lang)
  await expect(page.getByRole('heading', { name: label(lang, 'place.title') })).toBeVisible()
  await send(page, lang)
  await expect(page.locator(`article[data-outcome="${outcome}"]`)).toBeVisible()
}

for (const lang of ['en', 'fil'] as const) {
  test(`the copy rules hold on every screen and outcome, ${lang === 'en' ? 'English' : 'Taglish'}`, async ({ page, mocks }, testInfo) => {
    await choose(page, { lang })
    const check = (where: string) => expectClean(page, lang, where, testInfo)

    // The map with every kind of pin, its list, a live pin and the flag dialog, and the demo pin.
    mocks.behaviour.pins = pinSpecs()
    await page.goto('/#/map')
    await expect(page.locator('.map-pin')).toHaveCount(4)
    await check('#/map')
    await page.getByRole('button', { name: label(lang, 'map.list'), exact: true }).click()
    await expect(page.getByRole('list', { name: label(lang, 'map.listLabel') })).toBeVisible()
    await check('#/map, the list')
    await page.goto(`/#/pin/${LIVE_PIN.id}`)
    await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
    await check('#/pin, a live pin')
    await page.getByRole('button', { name: label(lang, 'pin.flag'), exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await check('the flag dialog')
    await page.keyboard.press('Escape')
    await page.goto(`/#/pin/${DEMO_PIN.id}`)
    await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
    await check('#/pin, the demo pin')
    mocks.behaviour.pins = []
    await page.goto('/#/map')
    await expect(page.getByRole('heading', { name: label(lang, 'map.empty.title') })).toBeVisible()
    await check('#/map, empty')

    // The pages that only read.
    for (const [route, key] of [
      ['/#/about', 'nav.about'],
      ['/#/privacy', 'privacy.title'],
      ['/#/licences', 'licences.title'],
    ] as const) {
      await page.goto(route)
      await expect(page.getByRole('heading', { name: label(lang, key), level: 1 })).toBeVisible()
      await expect(page.getByText(label(lang, 'licences.loading'))).toBeHidden()
      await check(route)
    }

    // Tested, the 18+ check, and a sample's three endings: a reading, a refusal in its frame, and a saved result.
    await page.goto('/#/tested')
    const first = page.getByRole('listitem').filter({ has: page.getByRole('button', { name: label(lang, 'sample.run'), exact: true }) }).first()
    await first.getByRole('button', { name: label(lang, 'sample.run'), exact: true }).click()
    await expect(page.getByRole('heading', { name: label(lang, 'consent.adultTitle') })).toBeVisible()
    await check('the 18+ check')
    await acceptAdult(page, lang)
    await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
    await check('#/tested, a sample\'s reading')
    for (const [name, setUp, outcome] of [
      ['a sample\'s refusal', (m: Mocks) => (m.behaviour.sampleOutcome = { kind: 'refused', reason: 'references_disagree' }), 'cant-tell'],
      ['a sample\'s saved result', (m: Mocks) => (m.behaviour.sampleRun = 'saved'), 'level'],
    ] as const) {
      setUp(mocks)
      await fresh(page, '/#/tested')
      await page.getByRole('button', { name: label(lang, 'sample.run'), exact: true }).first().click()
      await expect(page.locator(`article[data-outcome="${outcome}"]`)).toBeVisible()
      await check(`#/tested, ${name}`)
    }

    // The report flow: the notice, the camera, the place step, then every outcome of spec §4.2.
    await page.goto('/#/report')
    await expect(page.getByTestId('notice')).toBeVisible()
    await check('#/report, the notice')
    await acceptNotice(page, lang)
    await expect(page.getByRole('button', { name: label(lang, 'camera.shutter'), exact: true })).toBeEnabled()
    await check('#/report, the camera')
    await takePhoto(page, lang)
    await expect(page.getByRole('heading', { name: label(lang, 'place.title') })).toBeVisible()
    await check('#/report, the place step')
    await send(page, lang)
    await expect(page.locator('article[data-outcome="level"]')).toBeVisible()
    await check('#/report, a level')
    const outcomes: [string, (m: Mocks) => void, string][] = [
      ['a floor', (m) => (m.behaviour.outcome = { kind: 'level', key: 'floor' }), 'level'],
      ['below the gutter', (m) => (m.behaviour.outcome = { kind: 'level', key: 'below_gutter' }), 'level'],
      ['above the chest', (m) => (m.behaviour.outcome = { kind: 'level', key: 'above_chest' }), 'level'],
      ['outside Metro Manila', (m) => ((m.behaviour.outcome = { kind: 'level', key: 'knee' }), (m.behaviour.mode = 'private')), 'level'],
      ['no flood seen', (m) => ((m.behaviour.outcome = { kind: 'no_flood' }), (m.behaviour.mode = 'live')), 'no-flood'],
      ['can\'t tell', (m) => (m.behaviour.outcome = { kind: 'refused', reason: 'references_disagree' }), 'cant-tell'],
      ['processing failed', (m) => (m.behaviour.outcome = { kind: 'failed', reason: 'model_error' }), 'failed'],
      ['paused', (m) => (m.behaviour.outcome = { kind: 'failed', reason: 'model_calls_paused' }), 'paused'],
    ]
    for (const [name, setUp, outcome] of outcomes) {
      await report(page, mocks, lang, setUp, outcome)
      await check(`#/report, ${name}`)
    }
    // A sample run refused while uploads are paused.
    mocks.behaviour.sampleRun = 'paused'
    await fresh(page, '/#/tested')
    await page.getByRole('button', { name: label(lang, 'sample.run'), exact: true }).first().click()
    await expect(page.getByRole('main')).toContainText(label(lang, 'result.paused'))
    await check('#/tested, a sample run while uploads are paused')

    // Ask Lusot, empty and with answers, a crossing question among them (the notice is already accepted).
    await fresh(page, '/#/ask')
    await expect(page.getByRole('heading', { name: label(lang, 'nav.ask'), level: 1 })).toBeVisible()
    await check('#/ask')
    for (const question of ['Baha ba sa España cor. Maceda?', 'Lusot ba ang kotse sa Quiapo?', 'Kaya ba ng truck sa Marikina?']) {
      await page.getByRole('textbox', { name: label(lang, 'ask.ui.questionLabel') }).fill(question)
      const answered = page.waitForResponse((response) => new URL(response.url()).pathname === '/ask')
      await page.getByRole('button', { name: label(lang, 'ask.ui.send'), exact: true }).click()
      await answered
      await expect(page.getByRole('region', { name: label(lang, 'ask.ui.answer') })).toBeVisible()
      await expect(page.getByText(label(lang, 'ask.ui.asking'))).toHaveCount(0)
      await check(`#/ask, "${question}"`)
    }

    // An upload refused while uploads are paused.
    mocks.behaviour.upload = 'paused'
    await fresh(page, '/#/report')
    await takePhoto(page, lang)
    await send(page, lang)
    await expect(page.getByRole('heading', { name: label(lang, 'report.notSent') })).toBeVisible()
    await check('#/report, uploads paused')
  })
}
