// The Tested page's figures (spec C616): MS6's summary.json of the sealed run, read when the app is built, never typed
// by hand (W17). `@eval-results` is the repo's eval/results, which exists only from the sealed run (MS6 §4.3); before
// that each glob below gives {} and the page says when the results will appear. Task 18's builds point the alias at
// app/e2e/fixtures/eval-results/<state> instead (vite.config.ts). MS6 writes run.json beside report/, and a disclosed
// rerun's pair under rerun/ (MS6's C421).
import type { Translate } from '../copy/wording'
import type { Text } from '../i18n'

// k of n, as MS6 writes every rate.
export type Rate = { k: number; n: number }
export type ConfigurationName = 'landmark' | 'geometry'

// One configuration's Set A figures. A figure in the wrong shape is left out, and the page shows the rest: exact and
// within_one are M1's, shown when present.
export type Configuration = {
  underestimation?: Rate
  passability?: Rate
  coverage?: Rate
  exact?: Rate
  within_one?: Rate
  refused?: number
  failed?: number
}

// Set B's wheels: inches are decimal strings, as MS6's fmt_inches rounds them, or null with no wheel measured.
export type SetB = {
  wheels?: number
  measured?: Rate
  envelope?: Rate
  median_error_in: string | null
  worst_error_in: string | null
}

// summary.json as MS6's report.py writes it (its fixture at eval/tests/fixtures/small_run). Set A's figures, and the
// gate's answers, are null in a folder with only Set B (MS6 §4.4); a configuration left out of `configurations` was
// dropped (MS6's C418). Only a summary that passed loadSummary's gate takes this type, so kind is "sealed" and there
// is no synthetic flag.
export type Summary = {
  kind: 'sealed'
  rerun: boolean
  date: string
  rules_version: string | null
  shipped: ConfigurationName | null
  geometry_stays: boolean | null
  inches_shown: boolean | null
  baseline_level: string | null
  baseline_class: string | null
  configurations: Partial<Record<ConfigurationName, Configuration>> | null
  set_b: SetB | null
}

export type SummaryFiles = { summary?: unknown; run?: unknown; rerunSummary?: unknown; rerunRun?: unknown }

// The full report's link: undefined, the placeholder, until the submission repository exists (MS8-Q2's default, by
// Nov 2). Task 23 Step 5a sets it before the final build MS7 scans on Nov 3. Until then no report link renders.
export const REPORT_URL: string | undefined = undefined

type Json = Record<string, unknown>

const isJson = (value: unknown): value is Json => typeof value === 'object' && value !== null && !Array.isArray(value)
const count = (value: unknown): value is number => Number.isInteger(value) && (value as number) >= 0
const flag = (value: unknown): boolean | null => (typeof value === 'boolean' ? value : null)
const word = (value: unknown): string | null => (typeof value === 'string' ? value : null)
// MS6 writes "synthetic": false in a real run's summary, and may leave it out of run.json. Anything else fails closed.
const notSynthetic = (value: unknown): boolean => value === undefined || value === false

function rateOf(value: unknown): Rate | undefined {
  if (!isJson(value)) return undefined
  const { k, n } = value
  return count(k) && count(n) && k <= n ? { k, n } : undefined
}

function inchesOf(value: unknown): string | null {
  return typeof value === 'string' && /^\d+(\.\d+)?$/.test(value) ? value : null
}

function configurationOf(value: unknown): Configuration | undefined {
  if (!isJson(value)) return undefined
  const figures: Configuration = {}
  for (const name of ['underestimation', 'passability', 'coverage', 'exact', 'within_one'] as const) {
    const rate = rateOf(value[name])
    if (rate !== undefined) figures[name] = rate
  }
  if (count(value.refused)) figures.refused = value.refused
  if (count(value.failed)) figures.failed = value.failed
  return figures
}

function configurationsOf(value: unknown): Summary['configurations'] {
  if (!isJson(value)) return null
  const configurations: Partial<Record<ConfigurationName, Configuration>> = {}
  for (const name of ['landmark', 'geometry'] as const) {
    const figures = configurationOf(value[name])
    if (figures !== undefined) configurations[name] = figures
  }
  return configurations
}

function setBOf(value: unknown): SetB | null {
  if (!isJson(value)) return null
  const setB: SetB = { median_error_in: inchesOf(value.median_error_in), worst_error_in: inchesOf(value.worst_error_in) }
  if (count(value.wheels)) setB.wheels = value.wheels
  const measured = rateOf(value.measured)
  if (measured !== undefined) setB.measured = measured
  const envelope = rateOf(value.envelope)
  if (envelope !== undefined) setB.envelope = envelope
  return setB
}

// The summary the page may show, or null. A rerun replaces the first run (MS6's C421): with either of its files
// present, only the rerun's pair counts, and a rerun that fails the gate never brings the first run's figures back.
// The pair passes only when both files are there, both say kind "sealed", and neither has synthetic: true (MS6's
// C422, whose committed fixture carries the flag in both).
export function loadSummary(files: SummaryFiles): Summary | null {
  const rerun = files.rerunSummary !== undefined || files.rerunRun !== undefined
  const summary = rerun ? files.rerunSummary : files.summary
  const run = rerun ? files.rerunRun : files.run
  if (!isJson(summary) || !isJson(run)) return null
  if (summary.kind !== 'sealed' || run.kind !== 'sealed') return null
  if (!notSynthetic(summary.synthetic) || !notSynthetic(run.synthetic)) return null
  if (typeof summary.date !== 'string') return null
  const shipped = summary.shipped === 'landmark' || summary.shipped === 'geometry' ? summary.shipped : null
  return {
    kind: 'sealed',
    rerun: summary.rerun === true,
    date: summary.date,
    rules_version: word(summary.rules_version),
    shipped,
    geometry_stays: flag(summary.geometry_stays),
    inches_shown: flag(summary.inches_shown),
    baseline_level: word(summary.baseline_level),
    baseline_class: word(summary.baseline_class),
    configurations: configurationsOf(summary.configurations),
    set_b: setBOf(summary.set_b),
  }
}

// "12 of 20 (60%)": the share rounded half up to 0.1%, as MS6's fmt_rate rounds it, with a whole number shown without
// its ".0" ("3 of 17 (17.6%)"). "0 of 0" has no share.
export function rateText(t: Translate, { k, n }: Rate): Text {
  if (n === 0) return t('tested.rateNoShare', { k, n })
  const tenths = Math.floor((2000 * k + n) / (2 * n)) // round(1000k / n), half up, in whole numbers
  // A whole number of tenths over 10 prints as "60" or "17.6", never with a long tail.
  return t('tested.rate', { k, n, percent: String(tenths / 10) })
}

// Vite keys an alias glob by its root-relative path, so each file is read by its first (and only) value, never a key.
const only = (files: Record<string, unknown>): unknown => Object.values(files)[0]

export const SUMMARY: Summary | null = loadSummary({
  summary: only(import.meta.glob('@eval-results/report/summary.json', { eager: true, import: 'default' })),
  run: only(import.meta.glob('@eval-results/run.json', { eager: true, import: 'default' })),
  rerunSummary: only(import.meta.glob('@eval-results/rerun/report/summary.json', { eager: true, import: 'default' })),
  rerunRun: only(import.meta.glob('@eval-results/rerun/run.json', { eager: true, import: 'default' })),
})
