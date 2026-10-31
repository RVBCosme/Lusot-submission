import { beforeEach, describe, expect, it } from 'vitest'
import type { Pin } from '../lib/api'
import type { OwnPin } from '../report/flow'
import { offsetM } from '../test/geo'
import {
  flagCount,
  isOwn,
  markFlagged,
  mergeOwnPin,
  nearbyCount,
  newestFirst,
  pinStrength,
  readPinId,
  resetPinMemory,
  wasFlagged,
} from './pins'

const NOW = new Date('2026-10-30T10:00:00.000Z')
const HERE = { lat: 14.6095, lng: 120.9894 }
const MIN = 60_000

const ago = (minutes: number) => new Date(NOW.getTime() - minutes * MIN).toISOString()

function pin(over: Partial<Pin> = {}): Pin {
  return {
    id: 'r_a',
    ...HERE,
    capturedAt: ago(10),
    mode: 'live',
    flags: 0,
    gpsAccuracyM: 10,
    level: 'knee',
    landmark: 'rim_three_quarters',
    passability: 'NPLV',
    levelIsFloor: false,
    basis: { vehicles: 1, people: 0 },
    ...over,
  }
}

function ownPin(over: Partial<OwnPin> = {}): OwnPin {
  return { ...pin({ id: 'r_own', capturedAt: '2026-10-30T09:59:12.345Z' }), own: true, ...over }
}

beforeEach(() => resetPinMemory())

describe('pinStrength', () => {
  it('is full at 59 minutes, faded at 61 minutes and gone at 3 hours, for a live pin', () => {
    expect(pinStrength(pin({ capturedAt: ago(59) }), NOW)).toBe('full')
    expect(pinStrength(pin({ capturedAt: ago(61) }), NOW)).toBe('faded')
    expect(pinStrength(pin({ capturedAt: ago(180) }), NOW)).toBe('gone')
  })

  it('fades from exactly 1 hour and is gone from exactly 3 hours, with the minute before each still as it was', () => {
    expect(pinStrength(pin({ capturedAt: ago(60) }), NOW)).toBe('faded')
    expect(pinStrength(pin({ capturedAt: ago(179.9) }), NOW)).toBe('faded')
    expect(pinStrength(pin({ capturedAt: ago(59.9) }), NOW)).toBe('full')
    expect(pinStrength(pin({ capturedAt: ago(181) }), NOW)).toBe('gone')
  })

  it('is full for a demo pin at any age, an old photo included', () => {
    const demo = (capturedAt: string) => pin({ mode: 'demo', capturedAt, credit: 'Photo: someone' })
    expect(pinStrength(demo('2009-09-26T01:30:00Z'), NOW)).toBe('full')
    expect(pinStrength(demo(ago(5)), NOW)).toBe('full')
    expect(pinStrength(demo(ago(600)), NOW)).toBe('full')
  })

  it('is full for a photo time a little ahead of the clock, and gone for a time that does not read as a date', () => {
    expect(pinStrength(pin({ capturedAt: ago(-2) }), NOW)).toBe('full')
    expect(pinStrength(pin({ capturedAt: 'yesterday' }), NOW)).toBe('gone')
  })
})

describe('flagCount', () => {
  it('records the count and gives the highest count seen for that pin', () => {
    expect(flagCount('r_a', 3)).toBe(3)
    expect(flagCount('r_a', 2)).toBe(3)
    expect(flagCount('r_a', 1)).toBe(3)
    expect(flagCount('r_a', 4)).toBe(4)
    expect(flagCount('r_a', 0)).toBe(4)
  })

  it('counts each pin on its own', () => {
    expect(flagCount('r_a', 5)).toBe(5)
    expect(flagCount('r_b', 1)).toBe(1)
    expect(flagCount('r_a', 0)).toBe(5)
  })

  it('reads a count that is not a whole number of flags as none', () => {
    expect(flagCount('r_a', Number.NaN)).toBe(0)
    expect(flagCount('r_a', -2)).toBe(0)
    expect(flagCount('r_a', undefined as unknown as number)).toBe(0)
    expect(flagCount('r_a', 2)).toBe(2)
    expect(flagCount('r_a', Number.NaN)).toBe(2)
  })

  it('forgets everything when the test helper resets it', () => {
    flagCount('r_a', 6)
    markFlagged('r_a')
    resetPinMemory()
    expect(flagCount('r_a', 1)).toBe(1)
    expect(wasFlagged('r_a')).toBe(false)
  })
})

describe('markFlagged', () => {
  it('remembers a pin as flagged for the visit, and only that pin', () => {
    expect(wasFlagged('r_a')).toBe(false)
    markFlagged('r_a')
    expect(wasFlagged('r_a')).toBe(true)
    expect(wasFlagged('r_b')).toBe(false)
  })
})

describe('mergeOwnPin', () => {
  it('gives the pins back when there is no own pin', () => {
    const pins = [pin()]
    expect(mergeOwnPin(pins)).toEqual(pins)
    expect(mergeOwnPin(pins, undefined)).toEqual(pins)
  })

  it('adds the own pin when the pins hold nothing for it', () => {
    const merged = mergeOwnPin([pin({ id: 'r_far', ...offsetM(HERE, 400, 0) })], ownPin(HERE))
    expect(merged.map((p) => p.id)).toEqual(['r_far', 'r_own'])
    expect(isOwn(merged[1] as Pin)).toBe(true)
    expect(isOwn(merged[0] as Pin)).toBe(false)
  })

  it('drops the own pin by id, however far apart or far in time the two copies are', () => {
    const copy = pin({ id: 'r_own', ...offsetM(HERE, 500, 0), capturedAt: ago(100) })
    expect(mergeOwnPin([copy], ownPin(HERE))).toEqual([copy])
  })

  it("without a matching id, drops it by the same whole second and a 12 m offset: the app's ...:12.345Z against the API's ...:12Z", () => {
    const api = pin({ id: 'r_other', ...offsetM(HERE, 12, 0), capturedAt: '2026-10-30T09:59:12Z' })
    expect(mergeOwnPin([api], ownPin(HERE))).toEqual([api])
  })

  it('keeps the own pin at 30 m, even in the same second', () => {
    const api = pin({ id: 'r_other', ...offsetM(HERE, 30, 0), capturedAt: '2026-10-30T09:59:12Z' })
    const merged = mergeOwnPin([api], ownPin(HERE))
    expect(merged.map((p) => p.id)).toEqual(['r_other', 'r_own'])
  })

  it('holds the 15 m rule at its edge: 14 m is the same pin and 16 m is not', () => {
    const at = (metres: number) => pin({ id: 'r_other', ...offsetM(HERE, metres, 0), capturedAt: '2026-10-30T09:59:12Z' })
    expect(mergeOwnPin([at(14)], ownPin(HERE)).map((p) => p.id)).toEqual(['r_other'])
    expect(mergeOwnPin([at(16)], ownPin(HERE)).map((p) => p.id)).toEqual(['r_other', 'r_own'])
  })

  it('keeps the own pin when the second differs, even at 5 m (the whole second is the rule, not the nearest)', () => {
    const next = pin({ id: 'r_other', ...offsetM(HERE, 5, 0), capturedAt: '2026-10-30T09:59:13Z' })
    expect(mergeOwnPin([next], ownPin(HERE)).map((p) => p.id)).toEqual(['r_other', 'r_own'])
    const before = pin({ id: 'r_other', ...offsetM(HERE, 5, 0), capturedAt: '2026-10-30T09:59:11Z' })
    expect(mergeOwnPin([before], ownPin(HERE)).map((p) => p.id)).toEqual(['r_other', 'r_own'])
  })

  it('keeps the own pin when a time does not read as a date, rather than matching two unreadable times', () => {
    const odd = pin({ id: 'r_other', ...HERE, capturedAt: 'later' })
    expect(mergeOwnPin([odd], ownPin({ ...HERE, capturedAt: 'later' })).map((p) => p.id)).toEqual(['r_other', 'r_own'])
  })

  it('leaves the list it was given as it was', () => {
    const pins = [pin()]
    mergeOwnPin(pins, ownPin(HERE))
    expect(pins).toHaveLength(1)
  })
})

describe('newestFirst', () => {
  it('sorts by the photo time, newest first, with an old demo photo last, and leaves the input alone', () => {
    const demo = pin({ id: 'r_demo', mode: 'demo', capturedAt: '2009-09-26T01:30:00Z', credit: 'c' })
    const old = pin({ id: 'r_old', capturedAt: ago(100) })
    const fresh = pin({ id: 'r_fresh', capturedAt: ago(3) })
    const mid = pin({ id: 'r_mid', capturedAt: ago(40) })
    const input = [demo, old, fresh, mid]
    expect(newestFirst(input).map((p) => p.id)).toEqual(['r_fresh', 'r_mid', 'r_old', 'r_demo'])
    expect(input.map((p) => p.id)).toEqual(['r_demo', 'r_old', 'r_fresh', 'r_mid'])
  })

  it('keeps the order of pins taken in the same second, and puts a time that is not a date last', () => {
    const a = pin({ id: 'r_a', capturedAt: ago(5) })
    const b = pin({ id: 'r_b', capturedAt: ago(5) })
    const bad = pin({ id: 'r_bad', capturedAt: 'soon' })
    const fresh = pin({ id: 'r_c', capturedAt: ago(1) })
    expect(newestFirst([bad, a, b, fresh]).map((p) => p.id)).toEqual(['r_c', 'r_a', 'r_b', 'r_bad'])
  })
})

describe('nearbyCount', () => {
  const centre = pin({ id: 'r_centre' })

  it('counts live pins within 300 m and 3 hours, and not the pin itself or demo pins', () => {
    const pins = [
      centre,
      pin({ id: 'r_1', ...offsetM(HERE, 100, 0), capturedAt: ago(5) }),
      pin({ id: 'r_2', ...offsetM(HERE, 0, 250), capturedAt: ago(120) }),
      pin({ id: 'r_demo', mode: 'demo', credit: 'c', ...offsetM(HERE, 50, 0), capturedAt: ago(5) }),
    ]
    expect(nearbyCount(centre, pins, NOW)).toBe(2)
  })

  it('stops at 300 m: 299 m counts and 301 m does not', () => {
    const at = (metres: number) => pin({ id: 'r_x', ...offsetM(HERE, metres, 0) })
    expect(nearbyCount(centre, [at(299)], NOW)).toBe(1)
    expect(nearbyCount(centre, [at(301)], NOW)).toBe(0)
  })

  it('stops at 3 hours: 179 minutes counts, 3 hours does not, and an older pin does not either', () => {
    const at = (minutes: number) => pin({ id: 'r_x', ...offsetM(HERE, 10, 0), capturedAt: ago(minutes) })
    expect(nearbyCount(centre, [at(179)], NOW)).toBe(1)
    expect(nearbyCount(centre, [at(180)], NOW)).toBe(0)
    expect(nearbyCount(centre, [at(240)], NOW)).toBe(0)
  })

  it('counts a faded pin, and leaves the pin itself out by its id even when it sits among them', () => {
    const faded = pin({ id: 'r_f', ...offsetM(HERE, 10, 0), capturedAt: ago(90) })
    expect(nearbyCount(centre, [centre, faded, { ...centre }], NOW)).toBe(1)
  })

  it('counts a demo pin as the centre in the same way, from the live pins around it', () => {
    const demo = pin({ id: 'r_demo', mode: 'demo', credit: 'c', capturedAt: '2009-09-26T01:30:00Z' })
    expect(nearbyCount(demo, [demo, pin({ id: 'r_1', ...offsetM(HERE, 20, 0) })], NOW)).toBe(1)
  })
})

describe('readPinId', () => {
  it('gives an id only when the pins hold it', () => {
    const pins = [pin({ id: 'r_a' }), pin({ id: 'r_b' })]
    expect(readPinId(pins, 'r_b')).toBe('r_b')
    expect(readPinId(pins, 'r_zzz')).toBeUndefined()
    expect(readPinId([], 'r_a')).toBeUndefined()
  })
})
