// The Tested page's test fixtures, for tests only. Each is a summary.json with its run.json, laid out as MS6 writes
// them (run.json beside report/, MS6 §4.3), with MS6's keys. Every figure in them is made up: round numbers and dates
// in 2000. `sealed` and `rerun` say kind "sealed" with no synthetic flag, so only a test ever hands them to
// loadSummary; `synthetic` carries the flag in both files, as MS6's own committed fixture does.
const files = import.meta.glob<unknown>('./*/**/*.json', { eager: true, import: 'default' })

// MS6's committed fixture (eval/tests/fixtures/small_run), read, never copied: synthetic test data in both files.
const ms6 = import.meta.glob<unknown>(
  ['../../../../eval/tests/fixtures/small_run/report/summary.json', '../../../../eval/tests/fixtures/small_run/run.json'],
  { eager: true, import: 'default' },
)

export type FixturePair = { summary: unknown; run: unknown }

// A fresh copy each time, so a test can change it.
export function fixture(name: 'sealed' | 'rerun' | 'synthetic'): FixturePair {
  return {
    summary: structuredClone(files[`./${name}/report/summary.json`]),
    run: structuredClone(files[`./${name}/run.json`]),
  }
}

export function ms6Fixture(): FixturePair {
  const pick = (end: string) => structuredClone(Object.entries(ms6).find(([key]) => key.endsWith(end))?.[1])
  return { summary: pick('/report/summary.json'), run: pick('/small_run/run.json') }
}
