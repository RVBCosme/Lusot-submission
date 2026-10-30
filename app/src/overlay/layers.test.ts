import { describe, expect, it } from 'vitest'
import { DROP_CAUSES, LEVELS } from '../copy/levels'
import { dropLine } from '../copy/wording'
import { isScreenLineKey, makeT } from '../i18n'
import { EN } from '../i18n/en'
import { FIL } from '../i18n/fil'
import type { OverlayData, OverlayRef } from '../lib/api'
import { orderLayers, refChip, refLabel } from './layers'

const en = makeT('en')
const fil = makeT('fil')

// One reference with every layer, which a test then takes pieces from.
function ref(over: Partial<OverlayRef> = {}): OverlayRef {
  return {
    id: 1,
    kind: 'wheel',
    box: [10, 20, 110, 120],
    outline: [
      [
        [10, 20],
        [110, 20],
        [110, 120],
      ],
    ],
    landmark: 'hub',
    level: 'half_tire',
    level_from: 'landmark',
    level_is_floor: false,
    used: true,
    dropped: null,
    rechecked: false,
    rim_outline: [
      [
        [30, 40],
        [90, 40],
        [90, 100],
      ],
    ],
    rim: { center: [60, 70], axes: [60, 58], angle: 10 },
    waterline: [
      [10, 90],
      [110, 90],
    ],
    ...over,
  }
}

function data(refs: OverlayRef[], water: OverlayData['water'] = [[[0, 80], [200, 80], [200, 150]]]): OverlayData {
  return { version: 1, width: 200, height: 150, water, refs }
}

// A reference as the API client hands it over when the layers file lacks `level_is_floor` (MS4 rolls out first).
function withoutFloorKey(over: Partial<OverlayRef> = {}): OverlayRef {
  const { level_is_floor: _dropped, ...rest } = ref(over)
  return rest as OverlayRef
}

const summary = (layers: ReturnType<typeof orderLayers>) =>
  layers.map((layer) => (layer.kind === 'water' ? 'water' : `${layer.ref.id}:${layer.kind}`))

describe('orderLayers', () => {
  it("follows MS4's C524 order: water first, then each reference in refs order with its outline, rim outline, box, fitted rim, waterline and label", () => {
    const layers = orderLayers(data([ref({ id: 1 }), ref({ id: 2, kind: 'person' })]))
    expect(summary(layers)).toEqual([
      'water',
      '1:outline',
      '1:rim_outline',
      '1:box',
      '1:fitted_rim',
      '1:waterline',
      '1:label',
      '2:outline',
      '2:rim_outline',
      '2:box',
      '2:fitted_rim',
      '2:waterline',
      '2:label',
    ])
  })

  it('keeps the order refs came in, not the order of their ids', () => {
    const layers = orderLayers(data([ref({ id: 3 }), ref({ id: 1 }), ref({ id: 2 })]))
    const first = layers.filter((layer) => layer.kind === 'label').map((layer) => (layer.kind === 'label' ? layer.ref.id : 0))
    expect(first).toEqual([3, 1, 2])
  })

  it('skips each null layer: no rim outline, no fitted rim, no waterline, an empty outline, and an empty water', () => {
    const bare = ref({ rim_outline: null, rim: null, waterline: null })
    expect(summary(orderLayers(data([bare])))).toEqual(['water', '1:outline', '1:box', '1:label'])

    expect(summary(orderLayers(data([ref({ rim_outline: [] })])))).toEqual([
      'water',
      '1:outline',
      '1:box',
      '1:fitted_rim',
      '1:waterline',
      '1:label',
    ])
    expect(summary(orderLayers(data([ref({ outline: [] })])))).not.toContain('1:outline')
    expect(summary(orderLayers(data([ref()], [])))[0]).toBe('1:outline')
    expect(orderLayers(data([], []))).toEqual([])
  })

  it('accepts a layers file whose optional layers are missing altogether', () => {
    const { rim_outline: _a, rim: _b, waterline: _c, ...rest } = ref()
    const layers = orderLayers(data([rest as OverlayRef]))
    expect(summary(layers)).toEqual(['water', '1:outline', '1:box', '1:label'])
  })

  it('carries each layer its own geometry, as the file has it', () => {
    const one = ref()
    const layers = orderLayers(data([one]))
    const byKind = (kind: string) => layers.find((layer) => layer.kind === kind)
    expect(byKind('water')).toMatchObject({ polygons: [[[0, 80], [200, 80], [200, 150]]] })
    expect(byKind('outline')).toMatchObject({ polygons: one.outline })
    expect(byKind('rim_outline')).toMatchObject({ polygons: one.rim_outline })
    expect(byKind('box')).toMatchObject({ ref: { box: [10, 20, 110, 120] } })
    expect(byKind('fitted_rim')).toMatchObject({ rim: one.rim })
    expect(byKind('waterline')).toMatchObject({ line: one.waterline })
  })

  it('dims every layer of a reference that has a drop cause, and no other', () => {
    const layers = orderLayers(
      data([ref({ id: 1 }), ref({ id: 2, dropped: 'vehicle_moving', level: null, level_from: null, level_is_floor: null }), ref({ id: 3 })]),
    )
    const dimmed = (id: number) =>
      layers.filter((layer) => layer.kind !== 'water' && layer.ref.id === id).map((layer) => layer.kind !== 'water' && layer.dimmed)
    expect(dimmed(1).every((flag) => flag === false)).toBe(true)
    expect(dimmed(2)).toHaveLength(6)
    expect(dimmed(2).every((flag) => flag === true)).toBe(true)
    expect(dimmed(3).every((flag) => flag === false)).toBe(true)
  })

  it('leaves out a reference whose box cannot be placed or whose kind it cannot name, so a malformed file never throws', () => {
    const broken = ref({ id: 2, box: [1, 2, Number.NaN, 4] })
    const short = ref({ id: 3, box: [1, 2, 3] as unknown as OverlayRef['box'] })
    const face = ref({ id: 4, kind: 'face' as unknown as OverlayRef['kind'] })
    expect(summary(orderLayers(data([ref({ id: 1 }), broken, short, face])))).toEqual([
      'water',
      '1:outline',
      '1:rim_outline',
      '1:box',
      '1:fitted_rim',
      '1:waterline',
      '1:label',
    ])
  })
})

describe('refLabel', () => {
  it("gives a used wheel's landmark after its number, with the level in words", () => {
    expect(refLabel(en, ref({ id: 3 })).text).toBe(
      "Wheel 3: Half-tire. Water reaches the hub, about halfway up a parked car's wheel.",
    )
    expect(refLabel(en, ref({ id: 3, landmark: 'rim_three_quarters', level: 'knee' })).text).toBe(
      "Wheel 3: Knee. Water reaches three quarters of the way up a parked car's wheel rim.",
    )
  })

  it('adds that it was measured from the rim\'s size when the level came from geometry, and only then', () => {
    const geometry = refLabel(en, ref({ id: 1, landmark: 'rim_three_quarters', level: 'knee', level_from: 'geometry' }))
    expect(geometry.text).toBe(
      "Wheel 1: Knee. Water reaches three quarters of the way up a parked car's wheel rim. Measured from the size of the wheel rim.",
    )
    expect(refLabel(en, ref({ level_from: 'landmark' })).text).not.toContain('Measured from')
    expect(refLabel(en, ref({ level_from: null })).text).not.toContain('Measured from')
  })

  it('names a person and a car body by their kind', () => {
    expect(refLabel(en, ref({ id: 2, kind: 'person', landmark: 'knee', level: 'knee' })).text).toBe(
      'Person 2: Knee. Water reaches the knees of an adult in the photo.',
    )
    expect(refLabel(en, ref({ id: 4, kind: 'body', landmark: 'mid_door', level: 'half_tire' })).text).toMatch(/^Car body 4: /)
  })

  it('gives a dropped reference only its cause, with no level word, even when the file holds a level', () => {
    const dropped = ref({ id: 2, dropped: 'vehicle_moving', level: null, level_from: null, level_is_floor: null, landmark: null })
    expect(refLabel(en, dropped).text).toBe('Wheel 2: Not used, since the vehicle may be moving.')
    // The server nulls these on a dropped reference; the label doesn't depend on that.
    const stray = refLabel(en, ref({ id: 2, dropped: 'vehicle_moving', level: 'knee', level_from: 'geometry', level_is_floor: true }))
    expect(stray.text).toBe('Wheel 2: Not used, since the vehicle may be moving.')
    for (const label of [refLabel(en, dropped).text, stray.text]) {
      expect(label).not.toMatch(/knee|tire|gutter|chest|waist|deep|at least|measured/i)
    }
  })

  it('gives "Not used for this reading." for a cause it has no line for, and never the raw code', () => {
    const unknown = refLabel(en, ref({ id: 2, dropped: 'some_new_cause', level: null, level_from: null, level_is_floor: null }))
    expect(unknown.text).toBe('Wheel 2: Not used for this reading.')
    expect(unknown.text).not.toContain('some_new_cause')
    expect(unknown.text).not.toContain('_')
  })

  it("gives each cause the pipeline writes its own line from Task 8's table, not the general one", () => {
    for (const cause of DROP_CAUSES) {
      const label = refLabel(en, ref({ dropped: cause, level: null, level_from: null, level_is_floor: null })).text
      expect(label, cause).toBe(`Wheel 1: ${dropLine(en, cause).text}`)
      expect(label, cause).not.toBe('Wheel 1: Not used for this reading.')
    }
  })

  describe('a floor reading, by the layers file\'s level_is_floor', () => {
    const floor = (over: Partial<OverlayRef>) =>
      refLabel(en, ref({ id: 1, kind: 'body', landmark: 'window', level: 'tire', level_from: 'landmark', ...over })).text

    it('true reads "At least {level}", as the result card does', () => {
      expect(floor({ level_is_floor: true })).toBe('Car body 1: At least tire. Water reaches the windows of a parked car.')
    })

    it('false, null and absent read as the level itself, never as a floor', () => {
      const exact = 'Car body 1: Tire. Water reaches the windows of a parked car.'
      expect(floor({ level_is_floor: false })).toBe(exact)
      expect(floor({ level_is_floor: null })).toBe(exact)
      expect(refLabel(en, withoutFloorKey({ id: 1, kind: 'body', landmark: 'window', level: 'tire' })).text).toBe(exact)
    })

    it('words the two levels outside MMDA\'s gauge as a floor too, and takes the level from the card\'s level names', () => {
      expect(floor({ level_is_floor: true, level: 'above_chest', landmark: null })).toBe('Car body 1: At least above chest.')
      expect(floor({ level_is_floor: true, level: 'below_gutter', landmark: null })).toBe('Car body 1: At least below gutter.')
      for (const level of LEVELS) {
        expect(floor({ level_is_floor: true, level, landmark: null })).toContain(
          `At least ${EN[`result.levelName.${level}`].text}`,
        )
      }
    })

    it('is not a floor when the reference was dropped, whatever the flag says', () => {
      expect(floor({ level_is_floor: true, dropped: 'vehicle_moving' })).not.toMatch(/At least/)
    })

    it('reads "Hindi bababa sa {level}" in Taglish', () => {
      const label = refLabel(fil, ref({ id: 1, kind: 'body', landmark: null, level: 'tire', level_is_floor: true })).text
      expect(label).toContain('Hindi bababa sa tire')
      expect(label).toContain(FIL['overlay.ref.body'].text.replace('{id}', '1'))
    })
  })

  it('gives no landmark sentence for a landmark it has no line for, and no raw code', () => {
    const label = refLabel(en, ref({ id: 5, landmark: 'not_visible', level: 'knee' })).text
    expect(label).toBe('Wheel 5: Knee.')
    expect(refLabel(en, ref({ id: 5, landmark: null, level: 'knee' })).text).toBe('Wheel 5: Knee.')
    expect(refLabel(en, ref({ id: 5, landmark: 'made_up', level: 'knee' })).text).not.toContain('made_up')
  })

  it("gives only the number's name for a reference with no level and no cause", () => {
    expect(refLabel(en, ref({ id: 6, kind: 'person', landmark: null, level: null, level_from: null, level_is_floor: null })).text).toBe(
      'Person 6',
    )
    expect(refLabel(en, ref({ id: 6, landmark: 'not_visible', level: null })).text).toBe('Wheel 6')
  })

  it('is in the language of the screen, and carries that language', () => {
    const dropped = ref({ id: 2, dropped: 'vehicle_moving', level: null, level_from: null, level_is_floor: null })
    expect(refLabel(fil, dropped)).toEqual({
      text: `${FIL['overlay.ref.wheel'].text.replace('{id}', '2')}: ${FIL['dropped.vehicle_moving'].text}`,
      lang: 'fil',
    })
    expect(refLabel(en, dropped).lang).toBe('en')
  })

  it('uses no banned word, names no road or route, and gives no crossing advice, whatever it is given', () => {
    const labels: string[] = []
    for (const t of [en, fil]) {
      for (const kind of ['wheel', 'body', 'person'] as const) {
        for (const level of [...LEVELS, null]) {
          for (const floor of [true, false, null]) {
            for (const level_from of ['landmark', 'geometry', null] as const) {
              labels.push(refLabel(t, ref({ kind, level, level_is_floor: floor, level_from })).text)
              labels.push(refChip(t, ref({ kind, level, level_is_floor: floor, level_from })).text)
            }
          }
        }
      }
      for (const cause of [...DROP_CAUSES, 'unknown_cause']) {
        labels.push(refLabel(t, ref({ dropped: cause })).text, refChip(t, ref({ dropped: cause })).text)
      }
    }
    for (const label of labels) {
      expect(label).not.toMatch(/safe|ligtas/i)
      expect(label).not.toMatch(/\b(roads?|routes?|streets?|approach|cross|go ahead|wade)\b|kalsada|tumawid/i)
      expect(label).not.toMatch(/undefined|null|NaN|\{|\}/)
    }
  })
})

describe("the overlay's new lines", () => {
  const KEYS = [
    'overlay.title',
    'overlay.water',
    'overlay.ref.wheel',
    'overlay.ref.body',
    'overlay.ref.person',
    'overlay.floor',
    'overlay.notUsed',
  ] as const
  const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort()

  it('exist in both languages, start unreviewed, and keep to the product rules', () => {
    for (const key of KEYS) {
      for (const [lang, entry] of [['en', EN[key]], ['fil', FIL[key]]] as const) {
        expect(entry.text.trim(), `${lang} ${key}`).not.toBe('')
        expect(entry.reviewed, `${lang} ${key}`).toBe(false)
        expect(entry.text, `${lang} ${key}`).not.toMatch(/safe|ligtas/i)
        expect(entry.text, `${lang} ${key}`).not.toMatch(/(roads?|routes?|streets?|cross|approach)|kalsada|tumawid/i)
      }
      expect(placeholders(FIL[key].text), key).toEqual(placeholders(EN[key].text))
      // Not a screen-line key, so a Taglish screen shows the Taglish draft, as it does for the other result lines.
      expect(isScreenLineKey(key), key).toBe(false)
    }
  })

  it("give a floor the words the result card and the tracker's M20 review gave it", () => {
    expect(EN['overlay.floor'].text).toBe('At least {level}')
    expect(FIL['overlay.floor'].text).toBe('Hindi bababa sa {level}')
  })
})

describe('refChip, the short words on a box', () => {
  it('is the number and the level, or "At least" the level for a floor', () => {
    expect(refChip(en, ref({ id: 3, level: 'knee' })).text).toBe('3: Knee')
    expect(refChip(en, ref({ id: 1, level: 'tire', level_is_floor: true })).text).toBe('1: At least tire')
    expect(refChip(en, ref({ id: 1, level: 'tire', level_is_floor: false })).text).toBe('1: Tire')
    expect(refChip(en, ref({ id: 1, level: 'tire', level_is_floor: null })).text).toBe('1: Tire')
    expect(refChip(en, withoutFloorKey({ id: 1, level: 'tire' })).text).toBe('1: Tire')
    expect(refChip(fil, ref({ id: 1, level: 'tire', level_is_floor: true })).text).toBe('1: Hindi bababa sa tire')
  })

  it('is the number and "Not used" for a dropped reference, with no level, and just the number with nothing to say', () => {
    expect(refChip(en, ref({ id: 2, dropped: 'person_not_adult', level: null, level_from: null })).text).toBe('2: Not used')
    expect(refChip(en, ref({ id: 2, dropped: 'person_not_adult', level: 'knee' })).text).toBe('2: Not used')
    expect(refChip(en, ref({ id: 7, level: null, level_from: null })).text).toBe('7')
    expect(refChip(fil, ref({ id: 2, dropped: 'x' })).text).toBe(`2: ${FIL['overlay.notUsed'].text}`)
  })
})
