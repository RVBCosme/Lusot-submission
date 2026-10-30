import { expect, it } from 'vitest'
import { makeT } from '../i18n'
import { fixture, ms6Fixture } from './__fixtures__/fixtures'
import summarySource from './summary.ts?raw'
import { loadSummary, rateText, REPORT_URL } from './summary'

const en = makeT('en')
const fil = makeT('fil')

type Json = Record<string, unknown>
const asJson = (value: unknown) => value as Json

// Every key path in a JSON value, objects only, such as "configurations.geometry.exact.k".
function keyPaths(value: unknown, prefix = ''): string[] {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return []
  return Object.entries(value).flatMap(([key, inner]) => [`${prefix}${key}`, ...keyPaths(inner, `${prefix}${key}.`)])
}

it("MS6's own committed fixture, synthetic in both files, gives no figures", () => {
  const { summary, run } = ms6Fixture()
  expect(asJson(summary).synthetic).toBe(true)
  expect(asJson(run).synthetic).toBe(true)
  expect(loadSummary({ summary, run })).toBeNull()
})

it("the app's fixtures have MS6's keys, and the sealed and rerun ones carry no synthetic flag", () => {
  const ms6 = ms6Fixture()
  const ms6Summary = keyPaths(ms6.summary).filter((path) => path !== 'synthetic').sort()
  for (const name of ['sealed', 'synthetic'] as const) {
    const { summary } = fixture(name)
    expect(keyPaths(summary).filter((path) => path !== 'synthetic').sort(), name).toEqual(ms6Summary)
  }
  // The rerun dropped geometry (MS6's C418), so its summary has no geometry configuration.
  const rerunPaths = keyPaths(fixture('rerun').summary).sort()
  expect(rerunPaths).toEqual(ms6Summary.filter((path) => !path.startsWith('configurations.geometry')))
  for (const name of ['sealed', 'rerun'] as const) {
    const { summary, run } = fixture(name)
    expect(Object.hasOwn(asJson(summary), 'synthetic'), name).toBe(false)
    expect(Object.hasOwn(asJson(run), 'synthetic'), name).toBe(false)
  }
})

it('the sealed fixture with its run.json gives its figures', () => {
  const summary = loadSummary(fixture('sealed'))
  expect(summary).not.toBeNull()
  expect(summary?.kind).toBe('sealed')
  expect(summary?.date).toBe('2000-01-01')
  expect(summary?.rerun).toBe(false)
  expect(summary?.shipped).toBe('geometry')
  expect(summary?.inches_shown).toBe(false)
  expect(summary?.geometry_stays).toBe(true)
  expect(summary?.configurations?.geometry?.underestimation).toEqual({ k: 10, n: 80 })
  expect(summary?.configurations?.geometry?.within_one).toEqual({ k: 70, n: 80 })
  expect(summary?.configurations?.landmark?.coverage).toEqual({ k: 70, n: 100 })
  expect(summary?.set_b?.median_error_in).toBe('1.00')
  expect(summary?.set_b?.measured).toEqual({ k: 50, n: 60 })
})

it('a summary is accepted only with kind "sealed", in both files', () => {
  const developmentSummary = fixture('sealed')
  asJson(developmentSummary.summary).kind = 'development'
  expect(loadSummary(developmentSummary)).toBeNull()

  const developmentRun = fixture('sealed')
  asJson(developmentRun.run).kind = 'development'
  expect(loadSummary(developmentRun)).toBeNull()

  const noKind = fixture('sealed')
  delete asJson(noKind.summary).kind
  expect(loadSummary(noKind)).toBeNull()
})

it('synthetic: true in either file gives no figures (C422)', () => {
  const inSummary = fixture('sealed')
  asJson(inSummary.summary).synthetic = true
  expect(loadSummary(inSummary)).toBeNull()

  const inRun = fixture('sealed')
  asJson(inRun.run).synthetic = true
  expect(loadSummary(inRun)).toBeNull()

  expect(loadSummary(fixture('synthetic'))).toBeNull()
})

it('a synthetic flag that is anything but false fails closed', () => {
  for (const flag of ['true', 1, null, 'yes']) {
    const pair = fixture('sealed')
    asJson(pair.summary).synthetic = flag
    expect(loadSummary(pair), String(flag)).toBeNull()
  }
  // MS6 writes "synthetic": false in a real run's summary.
  const real = fixture('sealed')
  asJson(real.summary).synthetic = false
  asJson(real.run).synthetic = false
  expect(loadSummary(real)).not.toBeNull()
})

it('no files, or a summary without its run.json, give no figures', () => {
  expect(loadSummary({})).toBeNull()
  expect(loadSummary({ summary: fixture('sealed').summary })).toBeNull()
  expect(loadSummary({ run: fixture('sealed').run })).toBeNull()
  expect(loadSummary({ summary: 'not an object', run: fixture('sealed').run })).toBeNull()
  const noDate = fixture('sealed')
  delete asJson(noDate.summary).date
  expect(loadSummary(noDate)).toBeNull()
})

it("the rerun's pair wins over the first run (MS6's C421)", () => {
  const first = fixture('sealed')
  const rerun = fixture('rerun')
  const summary = loadSummary({ ...first, rerunSummary: rerun.summary, rerunRun: rerun.run })
  expect(summary?.date).toBe('2000-01-02')
  expect(summary?.rerun).toBe(true)
  expect(summary?.shipped).toBe('landmark')
  expect(summary?.configurations?.geometry).toBeUndefined()
  expect(summary?.configurations?.landmark?.underestimation).toEqual({ k: 9, n: 90 })
})

it("a rerun that fails the gate gives no figures, never the first run's", () => {
  const first = fixture('sealed')
  const synthetic = fixture('rerun')
  asJson(synthetic.run).synthetic = true
  expect(loadSummary({ ...first, rerunSummary: synthetic.summary, rerunRun: synthetic.run })).toBeNull()

  const syntheticSummary = fixture('rerun')
  asJson(syntheticSummary.summary).synthetic = true
  expect(loadSummary({ ...first, rerunSummary: syntheticSummary.summary, rerunRun: syntheticSummary.run })).toBeNull()

  // Half a rerun, either half, is no rerun to show, and doesn't bring the first run back.
  expect(loadSummary({ ...first, rerunSummary: fixture('rerun').summary })).toBeNull()
  expect(loadSummary({ ...first, rerunRun: fixture('rerun').run })).toBeNull()
})

it('a folder with only Set B gives its figures, with no configurations (MS6 §4.4)', () => {
  const pair = fixture('sealed')
  Object.assign(asJson(pair.summary), {
    configurations: null,
    shipped: null,
    geometry_stays: null,
    inches_shown: null,
  })
  const summary = loadSummary(pair)
  expect(summary?.configurations).toBeNull()
  expect(summary?.shipped).toBeNull()
  expect(summary?.inches_shown).toBeNull()
  expect(summary?.set_b?.median_error_in).toBe('1.00')
})

it('a figure in the wrong shape is left out, and the rest stay', () => {
  const pair = fixture('sealed')
  const geometry = asJson(asJson(asJson(pair.summary).configurations).geometry)
  geometry.exact = { k: 9, n: 8 } // more than all
  geometry.within_one = { k: '7', n: 8 }
  delete geometry.passability
  asJson(asJson(pair.summary).set_b).median_error_in = 'about 1'
  const summary = loadSummary(pair)
  expect(summary?.configurations?.geometry?.exact).toBeUndefined()
  expect(summary?.configurations?.geometry?.within_one).toBeUndefined()
  expect(summary?.configurations?.geometry?.passability).toBeUndefined()
  expect(summary?.configurations?.geometry?.underestimation).toEqual({ k: 10, n: 80 })
  expect(summary?.set_b?.median_error_in).toBeNull()
})

it('rateText gives k of n with its share, rounded half up to 0.1% as MS6 rounds it, and no share for 0 of 0', () => {
  expect(rateText(en, { k: 12, n: 20 })).toEqual({ text: '12 of 20 (60%)', lang: 'en' })
  expect(rateText(en, { k: 0, n: 0 })).toEqual({ text: '0 of 0', lang: 'en' })
  expect(rateText(en, { k: 3, n: 17 }).text).toBe('3 of 17 (17.6%)')
  expect(rateText(en, { k: 1, n: 16 }).text).toBe('1 of 16 (6.3%)') // 6.25 rounds half up
  expect(rateText(en, { k: 1, n: 8 }).text).toBe('1 of 8 (12.5%)')
  expect(rateText(en, { k: 0, n: 5 }).text).toBe('0 of 5 (0%)')
  expect(rateText(en, { k: 5, n: 5 }).text).toBe('5 of 5 (100%)')
  expect(rateText(en, { k: 2, n: 3 }).text).toBe('2 of 3 (66.7%)')
  expect(rateText(fil, { k: 12, n: 20 }).lang).toBe('fil')
})

it('REPORT_URL starts as undefined, the placeholder, so no report link renders', () => {
  expect(REPORT_URL).toBeUndefined()
})

it('the four summary files are read through @eval-results with literal globs, each by its first value', () => {
  for (const path of ['report/summary.json', 'run.json', 'rerun/report/summary.json', 'rerun/run.json']) {
    expect(summarySource).toContain(`import.meta.glob('@eval-results/${path}', { eager: true, import: 'default' })`)
  }
  expect(summarySource).toContain('Object.values(')
})
