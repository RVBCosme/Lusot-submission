import { expect, it } from 'vitest'
import rulesPy from '../../../backend/analysis/src/lusot_analysis/rules.py?raw'
import { EN } from '../i18n/en'
import geometryPy from '../../../backend/analysis/src/lusot_analysis/pipeline/geometry.py?raw'
import measurePy from '../../../backend/analysis/src/lusot_analysis/pipeline/measure.py?raw'
import referencesPy from '../../../backend/analysis/src/lusot_analysis/pipeline/references.py?raw'
import typesPy from '../../../backend/analysis/src/lusot_analysis/pipeline/types.py?raw'
import waterlinePy from '../../../backend/analysis/src/lusot_analysis/pipeline/waterline.py?raw'
import {
  BODY_FLOORS,
  DROP_CAUSES,
  FAILED_REASONS,
  LEVELS,
  OFF_GAUGE,
  PASSABILITY,
  PEOPLE_LANDMARKS,
  REFUSED_REASONS,
  WHEEL_LANDMARKS,
} from './levels'

// The body of the Python literal that starts at `start` (for example `LEVELS: tuple[str, ...] = (`), up to the
// line that closes it. The tests fail if the literal moves or is renamed, rather than reading nothing.
function literalBody(source: string, start: string, close: string): string[] {
  const lines = source.split(/\r?\n/)
  const from = lines.findIndex((line) => line.startsWith(start))
  expect(from, `${start} is in the Python source`).toBeGreaterThanOrEqual(0)
  const to = lines.findIndex((line, i) => i > from && line.startsWith(close))
  expect(to, `${start} is closed`).toBeGreaterThan(from)
  return lines.slice(from + 1, to)
}

// A tuple of strings: each line holds one quoted entry, with an optional comment.
function tupleOf(source: string, name: string, annotation = ''): string[] {
  const body = literalBody(source, `${name}${annotation} = (`, ')')
  return body.map((line) => /^\s+"(\w+)",/.exec(line)?.[1]).filter((entry): entry is string => entry !== undefined)
}

// A dict of `"key": value` lines: each key with the rest of its line.
function dictOf(source: string, start: string): [string, string][] {
  return literalBody(source, start, '}').flatMap((line) => {
    const match = /^\s+"(\w+)":\s*(.*?),?\s*$/.exec(line)
    return match === null ? [] : [[match[1], match[2]] as [string, string]]
  })
}

it('LEVELS are the 9 levels of rules.py, in its order', () => {
  expect(LEVELS).toEqual(tupleOf(rulesPy, 'LEVELS', ': tuple[str, ...]'))
  expect(LEVELS).toHaveLength(9)
  expect(LEVELS[0]).toBe('below_gutter')
  expect(LEVELS[8]).toBe('above_chest')
})

it("PASSABILITY is rules.py's mapping, and has PATV for 3 levels, NPLV for 2 and NPATV for 4", () => {
  const python = dictOf(rulesPy, 'PASSABILITY: Mapping[str, str] = {').map(([level, cls]) => [level, cls.replaceAll('"', '')])
  expect(Object.entries(PASSABILITY)).toEqual(python)
  const classes = Object.values(PASSABILITY)
  expect(classes.filter((c) => c === 'PATV')).toHaveLength(3)
  expect(classes.filter((c) => c === 'NPLV')).toHaveLength(2)
  expect(classes.filter((c) => c === 'NPATV')).toHaveLength(4)
  expect(Object.keys(PASSABILITY)).toEqual([...LEVELS])
})

it('OFF_GAUGE is the two levels outside MMDA\'s gauge: the first and the last', () => {
  expect(OFF_GAUGE).toEqual(['below_gutter', 'above_chest'])
})

it("the landmark lists are the categories of Table 8's wheel, people and body rows that can read a level", () => {
  const wheels = dictOf(rulesPy, 'WHEEL_ROWS: Mapping[str, Reading | None] = {')
  const people = dictOf(rulesPy, 'PEOPLE_ROWS: Mapping[str, Reading | None] = {')
  const body = dictOf(rulesPy, 'BODY_ROWS: Mapping[str, Reading | None] = {')
  const reads = ([, value]: [string, string]) => value.startsWith('Reading(')
  expect(WHEEL_LANDMARKS).toEqual(wheels.filter(reads).map(([key]) => key))
  // C91 (draft): an adult's ankle reads no level any more, but a pin or sample stored before it can still carry
  // ankle as its landmark until it expires, so the app keeps that line.
  expect(PEOPLE_LANDMARKS).toEqual(['ankle', ...people.filter(reads).map(([key]) => key)])
  // Only a body waterline that reads as a floor can decide a level (C53). The rest read nothing.
  expect(BODY_FLOORS).toEqual(body.filter(reads).map(([key]) => key))
  expect(BODY_FLOORS).toEqual(['mid_door', 'window'])
  expect(WHEEL_LANDMARKS).toHaveLength(6)
  expect(PEOPLE_LANDMARKS).toHaveLength(7)
})

it("no landmark category is in two lists, so a landmark's line never depends on the kind", () => {
  const all = [...WHEEL_LANDMARKS, ...PEOPLE_LANDMARKS, ...BODY_FLOORS]
  expect(new Set(all).size).toBe(all.length)
  expect(all).toHaveLength(15)
})

it("the reasons are MS3a's refused and failed lists, with MS1's pipeline_not_built among the failed", () => {
  expect(REFUSED_REASONS).toEqual(tupleOf(typesPy, 'REFUSED_REASONS'))
  expect(FAILED_REASONS).toEqual([...tupleOf(typesPy, 'FAILED_REASONS'), 'pipeline_not_built'])
  expect(REFUSED_REASONS).toHaveLength(8)
  expect(FAILED_REASONS).toHaveLength(6)
})

// The causes the pipeline writes into a reference's `dropped`: evidence.py's `causes`, which pipeline/__init__.py builds
// from `apply_drops` (references.py), `measure_boxes` (measure.py, with `keep_reading`'s `wheel_methods_disagree` from
// geometry.py) and step 3's waterlines (waterline.py). Each is read as the literal one of those functions assigns, so a
// cause added to the Python without a line in the app, or a line for a cause that isn't written, fails the test below.
// Step 2's caps (`causes.append("vehicle_cap")`) drop boxes before they are numbered, so they never reach `dropped`
// and the patterns don't match them.
const CAUSE_ASSIGNMENTS = [
  /\bcause = "(\w+)"/g, // cause = "vehicle_moving"
  /\bcauses\[\w+\] = "(\w+)"/g, // causes[person_id] = "person_wading"
  /\.fromkeys\(\w+, "(\w+)"\)/g, // causes |= dict.fromkeys(own, "wheel_vehicle_dropped")
  /\bcounted(?:\.append\(| \+= \[)\([\w.]+, "(\w+)"\)/g, // counted.append((person.id, "person_no_reading"))
  /\bLiteral\["(\w+)"\]/g, // keep_reading's -> ... | Literal["wheel_methods_disagree"]
]

function pipelineCauses(sources: string[]): string[] {
  const found = sources.flatMap((source) =>
    CAUSE_ASSIGNMENTS.flatMap((pattern) => [...source.matchAll(pattern)].map((match) => match[1])),
  )
  return [...new Set(found)].sort()
}

it('the cause reader finds each way the pipeline assigns a cause, and leaves out what never reaches `dropped`', () => {
  const python = [
    'cause = "vehicle_moving"',
    'causes[person_id] = "person_wading"',
    'causes |= dict.fromkeys(own, "wheel_vehicle_dropped")',
    'counted.append((person.id, "person_no_reading"))',
    'counted += [(w, "wheel_x") for w, _ in vehicle.wheels]',
    '-> KeptReading | Literal["wheel_methods_disagree"] | None:',
    'level_from: Literal["landmark", "geometry"]',
    'causes.append("vehicle_cap")',
    'causes += ["person_cap"] * 2',
    'counted.append((vehicle.id, cause))',
    'cause = None',
  ].join('\n')
  expect(pipelineCauses([python])).toEqual([
    'person_no_reading',
    'person_wading',
    'vehicle_moving',
    'wheel_methods_disagree',
    'wheel_vehicle_dropped',
    'wheel_x',
  ])
})

it("the drop causes are the ones the pipeline writes into a dropped reference's `dropped`, and each has a line", () => {
  const written = pipelineCauses([referencesPy, measurePy, waterlinePy, geometryPy])
  expect(written).toHaveLength(15)
  expect(new Set(DROP_CAUSES).size).toBe(DROP_CAUSES.length)
  // Every cause the pipeline writes is in the app's list, and every cause in the list is written.
  expect([...DROP_CAUSES].sort()).toEqual(written)
  // Every line is one of those causes, or the general line for a cause the app doesn't know.
  const lines = Object.keys(EN)
    .filter((key) => key.startsWith('dropped.'))
    .map((key) => key.slice('dropped.'.length))
    .sort()
  expect(lines).toEqual([...written, 'other'].sort())
})
