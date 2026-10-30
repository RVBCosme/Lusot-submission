// Development mock data (MS5 Task 6): what every outcome, pin and sample looks like to the app. Nothing here runs at
// load time (only functions and literals), so a production build drops this module whole, and
// app/scripts/check-bundle.mjs proves it. No photo is stored: draw.ts makes every image at run time.
//
// Which state the mock is in is picked by a scenario name (see `scenarioNames`). Shapes and names follow MS4's
// committed answers (plan "Notes"): C507's readings, C524's layers file, §4.4's pins, C512's samples and C527's
// saved sample.
import { FAILED_REASONS, PASSABILITY, REFUSED_REASONS, type Level } from '../copy/levels'
import type { OverlayData, OverlayRef, Point, Polygon, Reading, SavedSample } from '../lib/api'

// Sent as a response header value, so the string is in the code as a literal that a bundle check can search for.
export const MOCK_MARKER = 'LUSOT_MOCK_API'
// Where the mock's upload and layers links point. `.invalid` never resolves, so a link that escapes the mock fails.
export const MOCK_FILES_ORIGIN = 'https://mock-files.invalid'
export const DEFAULT_SCENARIO = 'level_knee'

// The stored photo's size in the mock (the real one is up to 1,600 px on its longer side). Layers are in these pixels.
const WIDTH = 800
const HEIGHT = 600

export type LevelKey = 'knee' | 'landmark' | 'floor' | 'below_gutter' | 'above_chest'
type RefusedReason = (typeof REFUSED_REASONS)[number]
type FailedReason = (typeof FAILED_REASONS)[number]

export type Scenario =
  | `level_${LevelKey | 'private'}`
  | 'no_flood_seen'
  | 'pending_forever'
  | `refused_${RefusedReason}`
  | `failed_${FailedReason}`
  | 'uploads_paused'
  | 'device_limit'
  | 'global_cap'
  | 'throttled'
  | 'samples_none'
  | 'samples_one'
  | 'samples_two'
  | 'pins_none'

// Every scenario, the default first. `level_*` is the level a new report reads; `level_landmark` is a half-tire
// reading from the wheel's hub (no inches), `level_floor` a tire floor, `level_private` the default reading taken
// outside Metro Manila. `refused_*` and `failed_*` take each reason code. `pending_forever` never reaches a final
// status. `uploads_paused` is MS1's 503 on an upload and a sample run; `failed_model_calls_paused` ends a report with
// the paused reason and answers a sample run with its saved result (C527). `device_limit` and `global_cap` are C522's
// 429s, with the seconds to the next UTC hour as their Retry-After. `throttled` is API Gateway's code-less 429, on the
// first upload request and the first poll, with a Retry-After of 3 s. `samples_none`, `samples_one` and `samples_two`
// shorten the samples list (the default has three), and `pins_none` empties the map's seeded pins.
export function scenarioNames(): Scenario[] {
  return [
    'level_knee',
    'level_landmark',
    'level_floor',
    'level_below_gutter',
    'level_above_chest',
    'level_private',
    'no_flood_seen',
    'pending_forever',
    ...REFUSED_REASONS.map((reason): Scenario => `refused_${reason}`),
    ...FAILED_REASONS.map((reason): Scenario => `failed_${reason}`),
    'uploads_paused',
    'device_limit',
    'global_cap',
    'throttled',
    'samples_none',
    'samples_one',
    'samples_two',
    'pins_none',
  ]
}

export function assertScenario(name: string): asserts name is Scenario {
  if (!(scenarioNames() as string[]).includes(name)) {
    throw new Error(`Unknown mock scenario "${name}". Use one of: ${scenarioNames().join(', ')}`)
  }
}

// What GET /reports/{id} finally answers for a report that is new.
export type Outcome =
  | { kind: 'level'; key: LevelKey }
  | { kind: 'no_flood' }
  | { kind: 'refused'; reason: string }
  | { kind: 'failed'; reason: string }
  | { kind: 'pending' } // never final

export interface ScenarioConfig {
  outcome: Outcome
  // `private` is a photo taken outside Metro Manila (D14): shown to the person, never pinned.
  mode: 'live' | 'private'
  uploads: 'ok' | 'paused' | 'device_limit' | 'global_cap' | 'throttled'
  sampleCount: number
  // While model calls are paused a sample run answers its seeding run's saved result (C527).
  savedSamples: boolean
  pins: boolean
}

export function scenarioConfig(scenario: Scenario): ScenarioConfig {
  const config: ScenarioConfig = {
    outcome: { kind: 'level', key: 'knee' },
    mode: 'live',
    uploads: 'ok',
    sampleCount: SAMPLES.length,
    savedSamples: false,
    pins: true,
  }
  switch (scenario) {
    case 'level_private':
      config.mode = 'private'
      break
    case 'no_flood_seen':
      config.outcome = { kind: 'no_flood' }
      break
    case 'pending_forever':
      config.outcome = { kind: 'pending' }
      break
    case 'uploads_paused':
      config.uploads = 'paused'
      break
    case 'device_limit':
    case 'global_cap':
    case 'throttled':
      config.uploads = scenario
      break
    case 'samples_none':
      config.sampleCount = 0
      break
    case 'samples_one':
      config.sampleCount = 1
      break
    case 'samples_two':
      config.sampleCount = 2
      break
    case 'pins_none':
      config.pins = false
      break
    default:
      if (scenario.startsWith('refused_')) {
        config.outcome = { kind: 'refused', reason: scenario.slice('refused_'.length) }
      } else if (scenario.startsWith('failed_')) {
        const reason = scenario.slice('failed_'.length)
        config.outcome = { kind: 'failed', reason }
        config.savedSamples = reason === 'model_calls_paused'
      } else {
        config.outcome = { kind: 'level', key: scenario.slice('level_'.length) as LevelKey }
      }
  }
  return config
}

// ---- Overlay layers (MS4's C524) and the readings that go with them (C507) ----

// One numbered reference as the pipeline's evidence holds it. Its shape fixes where it sits in the picture.
type Shape = 'wheel' | 'adult' | 'child'
interface RefSpec {
  id: number
  shape: Shape
  landmark: string | null
  level: Level | null
  from: 'landmark' | 'geometry' | null
  used: boolean
  dropped: string | null
  inches?: [number, number]
  rechecked?: boolean
}

// The one reference that decides, read from its landmark.
function landmarkRef(shape: Shape, landmark: string, level: Level): RefSpec {
  return { id: 1, shape, landmark, level, from: 'landmark', used: true, dropped: null }
}

interface LevelFixture {
  level: Level
  landmark: string
  levelIsFloor: boolean
  levelFrom: 'landmark' | 'geometry'
  basis: { vehicles: number; people: number }
  inches?: [number, number]
  waterY: number
  hue: number
  refs: RefSpec[]
}

function levelFixture(key: LevelKey): LevelFixture {
  switch (key) {
    case 'knee':
      return {
        level: 'knee',
        landmark: 'rim_three_quarters',
        levelIsFloor: false,
        levelFrom: 'geometry',
        basis: { vehicles: 1, people: 1 },
        inches: [15, 18],
        waterY: 405,
        hue: 205,
        refs: [
          {
            id: 1,
            shape: 'wheel',
            landmark: 'rim_three_quarters',
            level: 'knee',
            from: 'geometry',
            used: true,
            dropped: null,
            inches: [15, 18],
            rechecked: true,
          },
          { id: 2, shape: 'adult', landmark: 'knee', level: 'knee', from: 'landmark', used: true, dropped: null },
          // A person who isn't an adult reads no level: the reference stays, dimmed, with its cause.
          { id: 3, shape: 'child', landmark: null, level: null, from: null, used: false, dropped: 'person_not_adult' },
        ],
      }
    case 'landmark':
      return {
        level: 'half_tire',
        landmark: 'hub',
        levelIsFloor: false,
        levelFrom: 'landmark',
        basis: { vehicles: 1, people: 0 },
        waterY: 440,
        hue: 25,
        refs: [landmarkRef('wheel', 'hub', 'half_tire')],
      }
    case 'floor':
      return {
        level: 'tire',
        landmark: 'wheel_covered',
        levelIsFloor: true,
        levelFrom: 'landmark',
        basis: { vehicles: 1, people: 0 },
        waterY: 345,
        hue: 280,
        refs: [landmarkRef('wheel', 'wheel_covered', 'tire')],
      }
    case 'below_gutter':
      return {
        level: 'below_gutter',
        landmark: 'tire_only',
        levelIsFloor: false,
        levelFrom: 'landmark',
        basis: { vehicles: 1, people: 0 },
        waterY: 485,
        hue: 150,
        refs: [landmarkRef('wheel', 'tire_only', 'below_gutter')],
      }
    case 'above_chest':
      return {
        level: 'above_chest',
        landmark: 'above_chest',
        levelIsFloor: false,
        levelFrom: 'landmark',
        basis: { vehicles: 0, people: 1 },
        waterY: 270,
        hue: 340,
        refs: [landmarkRef('adult', 'above_chest', 'above_chest')],
      }
  }
}

const WHEEL_CENTER: Point = [300, 420]
const WHEEL_RADIUS = 62
const RIM_RADIUS = 40

const BOXES: Record<Shape, [number, number, number, number]> = {
  wheel: [238, 358, 362, 482],
  adult: [560, 230, 640, 500],
  child: [660, 340, 710, 500],
}

function circle(center: Point, radius: number, sides = 14): Polygon {
  return Array.from({ length: sides }, (_, i): Point => {
    const angle = (2 * Math.PI * i) / sides
    return [Math.round(center[0] + radius * Math.cos(angle)), Math.round(center[1] + radius * Math.sin(angle))]
  })
}

function outlineOf(shape: Shape): Polygon {
  const [x0, y0, x1, y1] = BOXES[shape]
  if (shape === 'wheel') return circle(WHEEL_CENTER, WHEEL_RADIUS)
  const shoulder = y0 + Math.round((y1 - y0) * 0.25)
  const inset = Math.round((x1 - x0) * 0.3)
  return [
    [x0 + inset, y0],
    [x1 - inset, y0],
    [x1, shoulder],
    [x1 - 4, y1],
    [x0 + 4, y1],
    [x0, shoulder],
  ]
}

function waterOutline(waterY: number): Polygon[] {
  return [
    [
      [0, waterY],
      [160, waterY - 6],
      [320, waterY + 4],
      [480, waterY - 5],
      [640, waterY + 3],
      [WIDTH, waterY - 4],
      [WIDTH, HEIGHT],
      [0, HEIGHT],
    ],
  ]
}

function layerRef(spec: RefSpec, waterY: number): OverlayRef {
  const box = BOXES[spec.shape]
  const fitted = spec.shape === 'wheel' && spec.from === 'geometry'
  return {
    id: spec.id,
    kind: spec.shape === 'wheel' ? 'wheel' : 'person',
    box,
    outline: [outlineOf(spec.shape)],
    landmark: spec.landmark,
    level: spec.level,
    level_from: spec.from,
    used: spec.used,
    dropped: spec.dropped,
    rechecked: spec.rechecked ?? false,
    rim_outline: fitted ? [circle(WHEEL_CENTER, RIM_RADIUS)] : null,
    rim: fitted ? { center: WHEEL_CENTER, axes: [80.4, 77.8], angle: 12.5 } : null,
    waterline: spec.dropped === null ? [[box[0], waterY], [box[2], waterY]] : null,
  }
}

// Inches are in an answer only for a geometry reading, and only once the release gate passes (C515).
function inchesOf(fixture: LevelFixture): { depthInMin?: number; depthInMax?: number } {
  return fixture.inches === undefined ? {} : { depthInMin: fixture.inches[0], depthInMax: fixture.inches[1] }
}

function readingOf(spec: RefSpec): Reading {
  const reading: Reading = {
    id: spec.id,
    kind: spec.shape === 'wheel' ? 'wheel' : 'person',
    landmark: spec.landmark,
    level: spec.level,
    used: spec.used,
    dropped: spec.dropped,
  }
  // C507: inches null on a dropped reference, and present only on a deciding one whose level came from geometry.
  if (spec.dropped !== null) reading.inches = null
  else if (spec.inches !== undefined) reading.inches = spec.inches
  return reading
}

export function levelLayers(key: LevelKey): OverlayData {
  const { waterY, refs } = levelFixture(key)
  const water = waterOutline(waterY)
  return { version: 1, width: WIDTH, height: HEIGHT, water, refs: refs.map((ref) => layerRef(ref, waterY)) }
}

export function levelHue(key: LevelKey): number {
  return levelFixture(key).hue
}

// A dry street: no water and nothing numbered.
function dryLayers(): OverlayData {
  return { version: 1, width: WIDTH, height: HEIGHT, water: [], refs: [] }
}

// ---- Report answers ----

export interface ReportFacts {
  reportId: string
  mode: 'live' | 'private' | 'sample' | 'demo'
  published: boolean
  capturedAt: string
  gpsAccuracyM?: number
  // For a level result, while its links are issued (C503).
  links?: { photoUrl: string; overlayUrl: string; layersUrl: string }
  demo?: { credit: string; place?: string; event?: string }
}

export function pendingBody(status: 'pending' | 'processing', facts: ReportFacts): Record<string, unknown> {
  return { reportId: facts.reportId, status, mode: facts.mode, published: false, capturedAt: facts.capturedAt }
}

// GET /reports/{id}'s answer once the outcome is final (MS4's §4.3), or "processing" for the outcome that never is.
export function resultBody(outcome: Outcome, facts: ReportFacts): Record<string, unknown> {
  const body: Record<string, unknown> = {
    reportId: facts.reportId,
    status: 'processing',
    mode: facts.mode,
    published: facts.published,
    capturedAt: facts.capturedAt,
  }
  switch (outcome.kind) {
    case 'pending':
      body.published = false
      break
    case 'refused':
    case 'failed':
      body.status = outcome.kind
      body.published = false
      body.refusalReason = outcome.reason
      break
    case 'no_flood':
      body.status = 'done'
      body.published = false // C506: "no flood seen" isn't published
      body.noFloodSeen = true
      break
    case 'level': {
      const fixture = levelFixture(outcome.key)
      Object.assign(body, {
        status: 'done',
        noFloodSeen: false,
        level: fixture.level,
        landmark: fixture.landmark,
        passability: PASSABILITY[fixture.level],
        basis: fixture.basis,
        levelIsFloor: fixture.levelIsFloor,
        levelFrom: fixture.levelFrom,
        readings: fixture.refs.map(readingOf),
      })
      Object.assign(body, inchesOf(fixture))
      if (facts.gpsAccuracyM !== undefined) body.gpsAccuracyM = facts.gpsAccuracyM
      if (facts.links !== undefined) Object.assign(body, facts.links)
      if (facts.demo !== undefined) Object.assign(body, facts.demo)
      break
    }
  }
  return body
}

export function isoSeconds(ms: number): string {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z')
}

// ---- Public pins (MS4's §4.4) ----

export interface PinSpec {
  id: string
  lat: number
  lng: number
  // Minutes before the mock was made, or a fixed time for a demo pin's old photo.
  ageMin?: number
  fixedAt?: string
  mode: 'live' | 'demo'
  flags: number
  gpsAccuracyM: number | null
  key: LevelKey
  // A level that isn't one of the 9, which Task 5 drops.
  rawLevel?: string
  demo?: { credit: string; place: string; event: string }
}

// Fresh (10 and 25 min, 70 m apart), faded (90 min), past 3 hours (200 min, which the map hides), a demo pin, and
// one with a level the app can't word.
export function pinSpecs(): PinSpec[] {
  return [
    {
      id: 'r_1a2b3c4d5e6f40718293a4b5c6d7e8f9',
      lat: 14.6095,
      lng: 120.9894,
      ageMin: 10,
      mode: 'live',
      flags: 0,
      gpsAccuracyM: 12,
      key: 'knee',
    },
    {
      id: 'r_2b3c4d5e6f7a41829304b5c6d7e8f9a0',
      lat: 14.6101,
      lng: 120.9899,
      ageMin: 25,
      mode: 'live',
      flags: 2,
      gpsAccuracyM: 8,
      key: 'landmark',
    },
    {
      id: 'r_3c4d5e6f7a8b429304a5b6c7d8e9f0a1',
      lat: 14.6507,
      lng: 121.1029,
      ageMin: 90,
      mode: 'live',
      flags: 0,
      gpsAccuracyM: 20,
      key: 'floor',
    },
    {
      id: 'r_4d5e6f7a8b9c43a405b6c7d8e9f0a1b2',
      lat: 14.5547,
      lng: 121.0244,
      ageMin: 200,
      mode: 'live',
      flags: 1,
      gpsAccuracyM: 15,
      key: 'knee',
    },
    {
      id: 'r_5e6f7a8b9c0d44b506c7d8e9f0a1b2c3',
      lat: 14.6342,
      lng: 121.0965,
      fixedAt: '2009-09-26T01:30:00Z',
      mode: 'demo',
      flags: 0,
      gpsAccuracyM: null,
      key: 'above_chest',
      demo: {
        credit: 'Photo: Example Contributor (mock), CC BY 4.0, faces and plates blurred by Lusot',
        place: 'Marikina',
        event: 'Typhoon Ondoy',
      },
    },
    {
      id: 'r_6f7a8b9c0d1e45c607d8e9f0a1b2c3d4',
      lat: 14.5995,
      lng: 121.036,
      ageMin: 15,
      mode: 'live',
      flags: 0,
      gpsAccuracyM: 10,
      key: 'knee',
      rawLevel: 'ankle_deep',
    },
  ]
}

export function pinCapturedAt(spec: PinSpec, startedAt: number): string {
  return spec.fixedAt ?? isoSeconds(startedAt - (spec.ageMin ?? 0) * 60_000)
}

// What GET /map/pins holds for one pin. `flags` is the count so far.
export function pinBody(
  pin: {
    id: string
    lat: number
    lng: number
    capturedAt: string
    mode: 'live' | 'demo'
    gpsAccuracyM: number | null
    key: LevelKey
    rawLevel?: string
    demo?: { credit: string; place: string; event: string }
  },
  flags: number,
): Record<string, unknown> {
  const fixture = levelFixture(pin.key)
  const body: Record<string, unknown> = {
    id: pin.id,
    lat: pin.lat,
    lng: pin.lng,
    capturedAt: pin.capturedAt,
    mode: pin.mode,
    flags,
    gpsAccuracyM: pin.gpsAccuracyM,
    level: pin.rawLevel ?? fixture.level,
    landmark: fixture.landmark,
    passability: PASSABILITY[fixture.level],
    levelIsFloor: fixture.levelIsFloor,
    basis: fixture.basis,
  }
  Object.assign(body, inchesOf(fixture))
  if (pin.demo !== undefined) Object.assign(body, pin.demo)
  return body
}

// ---- Samples (MS4's C512) ----

export interface SampleSpec {
  sampleId: string
  credit: string
  license: string
  place: string
  date: string
  event?: string
  // What its seeding run read, saved for while model calls are paused (C527).
  seeded: Outcome
}

// One licence of each kind C617 allows. Every credit says it is a mock.
const SAMPLES: readonly SampleSpec[] = [
  {
    sampleId: 'sample-01',
    credit: 'Photo: Example Contributor (mock), CC0 1.0',
    license: 'CC0 1.0',
    place: 'Marikina',
    date: '2009-09-26',
    event: 'Typhoon Ondoy',
    seeded: { kind: 'level', key: 'knee' },
  },
  {
    sampleId: 'sample-02',
    credit: 'Photo: Example Contributor (mock), CC BY 4.0, faces and plates blurred by Lusot',
    license: 'CC BY 4.0',
    place: 'Quezon City',
    date: '2012-08-07',
    event: 'Habagat rains',
    seeded: { kind: 'no_flood' },
  },
  {
    sampleId: 'sample-03',
    credit: 'Photo: used with permission (mock), faces and plates blurred by Lusot',
    license: 'used with permission',
    place: 'Manila',
    date: '2026-10-05',
    seeded: { kind: 'level', key: 'landmark' },
  },
]

export function sampleList(count: number): readonly SampleSpec[] {
  return SAMPLES.slice(0, count)
}

// The picture a sample's photo link draws.
export function sampleScene(sample: SampleSpec): { layers: OverlayData; hue: number } {
  return sample.seeded.kind === 'level'
    ? { layers: levelLayers(sample.seeded.key), hue: levelHue(sample.seeded.key) }
    : { layers: dryLayers(), hue: 120 }
}

export const SAVED_AT = '2026-10-29T14:20:00Z'

// A sample's saved result (amendment 10): done or refused, the level fields only with a level, and no basis,
// overlay or inches.
export function savedSample(sample: SampleSpec): SavedSample {
  const result: SavedSample['result'] = { status: 'done' }
  if (sample.seeded.kind === 'level') {
    const fixture = levelFixture(sample.seeded.key)
    Object.assign(result, {
      noFloodSeen: false,
      level: fixture.level,
      landmark: fixture.landmark,
      passability: PASSABILITY[fixture.level],
      levelIsFloor: fixture.levelIsFloor,
    })
  } else {
    result.noFloodSeen = true
  }
  return { saved: true, savedAt: SAVED_AT, result }
}

export function levelKeyOf(outcome: Outcome): LevelKey | undefined {
  return outcome.kind === 'level' ? outcome.key : undefined
}
