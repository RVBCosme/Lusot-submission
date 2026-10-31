// The Tested page in each of its four builds (MS5 Task 18, C616, U7): the summary is fixed at build time, so each
// `tested-<state>` project runs this spec against its own build (playwright.config.ts). `none` and `synthetic` show no
// figure; `sealed-run` shows the sealed run's; `rerun` shows the rerun's and none of the first run's. Every figure is
// made up (e2e/fixtures/eval-results). The page never says "accuracy", and holds "Not affiliated with MMDA."
import { expect, test } from './mocks'
import { label } from './steps'

const L = 'en'

// The shipped configuration's five rates, then Set B's median and wheels, as each fixture's summary gives them.
const FIGURES: Record<string, { from: string; shipped: 'landmark' | 'geometry'; rates: string[]; median: string; notShown: string[] }> = {
  'sealed-run': {
    from: label(L, 'tested.results.from', { date: 'Jan 1, 2000' }),
    shipped: 'geometry',
    rates: ['10 of 80 (12.5%)', '60 of 80 (75%)', '80 of 100 (80%)', '40 of 80 (50%)', '70 of 80 (87.5%)'],
    median: label(L, 'tested.setB.medianValue', { inches: '1.00', n: 50 }),
    notShown: [],
  },
  rerun: {
    from: label(L, 'tested.results.rerunFrom', { date: 'Jan 2, 2000' }),
    shipped: 'landmark',
    rates: ['9 of 90 (10%)', '72 of 90 (80%)', '90 of 100 (90%)', '45 of 90 (50%)', '81 of 90 (90%)'],
    median: label(L, 'tested.setB.medianValue', { inches: '2.00', n: 50 }),
    // The first run's figures and date, which the rerun replaces (MS6's C421).
    notShown: ['10 of 80 (12.5%)', '70 of 80 (87.5%)', label(L, 'tested.results.from', { date: 'Jan 1, 2000' })],
  },
}

test('the Tested page shows what its build holds', async ({ page }, testInfo) => {
  const state = String(testInfo.project.metadata.summary)
  await page.goto('/#/tested')
  const main = page.getByRole('main')
  await expect(page.getByRole('heading', { name: label(L, 'nav.tested'), level: 1 })).toBeVisible()

  // Every build: how Lusot is tested, its known limits, the samples, and no "accuracy".
  await expect(page.getByRole('heading', { name: label(L, 'tested.how.title') })).toBeVisible()
  await expect(page.getByRole('heading', { name: label(L, 'tested.limits.title') })).toBeVisible()
  for (const key of ['tested.limits.night', 'tested.limits.rain', 'tested.limits.blur', 'tested.limits.faceBlur'] as const) {
    await expect(main).toContainText(label(L, key))
  }
  await expect(main).toContainText(label(L, 'about.notAffiliated'))
  await expect(page.getByRole('button', { name: label(L, 'sample.run'), exact: true }).first()).toBeVisible()
  expect(await main.innerText()).not.toMatch(/accuracy/i)
  // REPORT_URL is the placeholder until the submission repository exists, so no report link renders.
  await expect(page.getByRole('link', { name: label(L, 'tested.reportLink') })).toHaveCount(0)

  const figures = FIGURES[state]
  if (figures === undefined) {
    // No sealed run yet, or a synthetic one: the page says when the results appear, and shows no figure.
    expect(['none', 'synthetic']).toContain(state)
    await expect(main).toContainText(label(L, 'tested.pending'))
    await expect(main).not.toContainText(label(L, 'tested.indicative'))
    expect(await main.innerText()).not.toMatch(/\d+ of \d+/)
    return
  }

  await expect(main).not.toContainText(label(L, 'tested.pending'))
  await expect(main).toContainText(figures.from)
  await expect(main).toContainText(label(L, figures.shipped === 'geometry' ? 'tested.shipped.geometry' : 'tested.shipped.landmark'))
  const keys = [
    'tested.figure.underestimation',
    'tested.figure.passability',
    'tested.figure.coverage',
    'tested.figure.exact',
    'tested.figure.withinOne',
  ] as const
  for (const [i, key] of keys.entries()) {
    const row = page.locator('dl > div').filter({ hasText: label(L, key) })
    await expect(row).toContainText(figures.rates[i]!)
    // Every figure carries "indicative" (C616, W19).
    await expect(row).toContainText(label(L, 'tested.indicative'))
  }
  await expect(main).toContainText(label(L, 'tested.inches.notShown'))
  await expect(main).toContainText(figures.median)
  await expect(main).toContainText(label(L, 'tested.results.intro'))
  for (const text of figures.notShown) await expect(main).not.toContainText(text)
})
