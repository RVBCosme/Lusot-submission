import { expect, it } from 'vitest'
import { EN } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { makeT, type Lang } from '../i18n'
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
import {
  basisLine,
  classLine,
  dropLine,
  inchesLine,
  landmarkLine,
  levelFromLine,
  levelLine,
  reasonLine,
  referenceLine,
} from './wording'

const en = makeT('en')
const fil = makeT('fil')
const BOTH: [Lang, typeof en][] = [
  ['en', en],
  ['fil', fil],
]
const REASONS = [...REFUSED_REASONS, ...FAILED_REASONS]
const LANDMARKS = [...WHEEL_LANDMARKS, ...PEOPLE_LANDMARKS, ...BODY_FLOORS]

// The banned words and the crossing phrases are checked over every line of both tables by i18n.test.tsx, and every
// line below is built from those tables. These checks add what that one doesn't: road and route wording, and any
// telling of a person to go near water or traffic. D19's refusal is left out: it tells people what not to do.
const WHOLE_ROAD = /\b(roads?|routes?|streets?|highways?|lanes?)\b|kalsada|\bdaan\b|\bruta\b/i
const APPROACH =
  /\b(approach|walk|wade|wading|step|go to|drive|closer|enter)\b|lumapit|lumusong|pumunta|maglakad|magmaneho|pumasok/i

function resultAndReasonKeys(table: Record<string, unknown>): string[] {
  return Object.keys(table).filter((key) => key.startsWith('result.') || key.startsWith('reason.'))
}

it("the level lines are C81's, word for word", () => {
  expect(levelLine(en, 'knee', false).text).toBe('Knee deep at this spot (MMDA level).')
  expect(levelLine(en, 'tire', true).text).toBe('At least tire deep at this spot (MMDA level).')
  expect(levelLine(en, 'below_gutter', false).text).toBe('Below gutter deep at this spot.')
  expect(levelLine(en, 'above_chest', false).text).toBe('Above chest deep at this spot.')
  expect(classLine(en, 'knee').text).toBe('MMDA lists this level as not passable to light vehicles (NPLV).')
  expect(classLine(en, 'below_gutter').text).toBe(
    "Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).",
  )
  expect(classLine(en, 'above_chest').text).toBe(
    "Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).",
  )
  expect(basisLine(en, { vehicles: 1, people: 1 }).text).toBe('From 2 reference objects.')
  expect(inchesLine(en, 15, 18).text).toBe('Estimated 15 to 18 in.')
  expect(reasonLine(makeT('fil'), 'too_dark').lang).toBe('en') // unreviewed Taglish screen-line key
})

it('all 9 levels read in the same words as the test screen, shallowest first', () => {
  expect(LEVELS.map((level) => levelLine(en, level, false).text)).toEqual([
    'Below gutter deep at this spot.',
    'Gutter deep at this spot (MMDA level).',
    'Half-knee deep at this spot (MMDA level).',
    'Half-tire deep at this spot (MMDA level).',
    'Knee deep at this spot (MMDA level).',
    'Tire deep at this spot (MMDA level).',
    'Waist deep at this spot (MMDA level).',
    'Chest deep at this spot (MMDA level).',
    'Above chest deep at this spot.',
  ])
})

it('a floor reads "at least" for every level and keeps its marking', () => {
  expect(levelLine(en, 'half_tire', true).text).toBe('At least half-tire deep at this spot (MMDA level).')
  expect(levelLine(en, 'above_chest', true).text).toBe('At least above chest deep at this spot.')
  expect(levelLine(fil, 'tire', true).text).toMatch(/^Hindi bababa sa tire ang lalim/)
})

it('every level line, in both languages, says "at this spot", and only the two added levels lack "(MMDA level)"', () => {
  for (const [lang, t] of BOTH) {
    const spot = lang === 'en' ? 'at this spot' : 'sa spot na ito'
    for (const level of LEVELS) {
      for (const floor of [false, true]) {
        const line = levelLine(t, level, floor)
        expect(line.text, `${lang} ${level} ${floor}`).toContain(spot)
        expect(line.text.includes('(MMDA level)'), `${lang} ${level} ${floor}`).toBe(!OFF_GAUGE.includes(level))
        expect(line.lang).toBe(lang)
        expect(line.text, `${lang} ${level}`).not.toMatch(/\{\w+\}/)
      }
    }
  }
})

it('every level line starts with a capital letter, whichever words name the level', () => {
  for (const [, t] of BOTH) {
    for (const level of LEVELS) expect(levelLine(t, level, false).text).toMatch(/^\p{Lu}/u)
  }
})

it("the class line names the level's own class, and the two added levels name the MMDA level they lie beyond", () => {
  for (const [lang, t] of BOTH) {
    for (const level of LEVELS) {
      const line = classLine(t, level)
      expect(line.text, `${lang} ${level}`).toContain(`(${PASSABILITY[level]})`)
      expect(line.lang).toBe(lang)
      if (OFF_GAUGE.includes(level)) {
        const beyond = level === 'below_gutter' ? 'gutter' : 'chest'
        expect(line.text, `${lang} ${level}`).toContain(beyond)
      } else {
        expect(line.text, `${lang} ${level}`).not.toMatch(/gutter level|chest level/)
      }
    }
  }
  expect(classLine(en, 'gutter').text).toBe('MMDA lists this level as passable to all vehicles (PATV).')
  expect(classLine(en, 'half_tire').text).toBe('MMDA lists this level as not passable to light vehicles (NPLV).')
  expect(classLine(en, 'waist').text).toBe('MMDA lists this level as not passable to any vehicle (NPATV).')
})

// A class line is what MMDA lists, never a verdict on the spot. A draft that drops the source would read as one, and
// `result.*` keys aren't held back on a Taglish screen the way `reason.*` keys are, so it would show unreviewed.
it('every class line, in both tables, keeps MMDA as the source of the class', () => {
  const classKeys = (table: Record<string, unknown>) => Object.keys(table).filter((key) => key.startsWith('result.class.'))
  for (const [table, source] of [
    [EN, 'MMDA lists'],
    [FIL, 'ng MMDA'],
  ] as const) {
    const keys = classKeys(table)
    expect(keys).toHaveLength(5)
    for (const key of keys) {
      const { text } = (table as Record<string, { text: string }>)[key]
      expect(text, key).toContain(source)
    }
  }
})

it('no class line speaks of a road or of what a person may do', () => {
  for (const [, t] of BOTH) {
    for (const level of LEVELS) {
      expect(classLine(t, level).text).not.toMatch(APPROACH)
      expect(classLine(t, level).text).not.toMatch(WHOLE_ROAD)
    }
  }
})

it('the basis line counts vehicles and people together, and says "object" for one', () => {
  expect(basisLine(en, { vehicles: 2, people: 1 }).text).toBe('From 3 reference objects.')
  expect(basisLine(en, { vehicles: 1, people: 0 }).text).toBe('From 1 reference object.')
  expect(basisLine(en, { vehicles: 0, people: 1 }).text).toBe('From 1 reference object.')
  expect(basisLine(fil, { vehicles: 2, people: 2 }).text).toBe('Mula sa 4 reference object.')
  expect(basisLine(fil, { vehicles: 2, people: 2 }).lang).toBe('fil')
})

it('the inches line gives the range the API sent, and one number when both ends agree', () => {
  expect(inchesLine(en, 14.9, 18.2).text).toBe('Estimated 14.9 to 18.2 in.')
  expect(inchesLine(en, 15, 15).text).toBe('Estimated 15 in.')
  expect(inchesLine(fil, 15, 18).text).toBe('Tinatayang 15 hanggang 18 in.')
  expect(inchesLine(fil, 15, 15).text).toBe('Tinatayang 15 in.')
})

it('the geometry line shows only when geometry set the level', () => {
  expect(levelFromLine(en, 'geometry')?.text).toBe('Measured from the size of the wheel rim.')
  expect(levelFromLine(fil, 'geometry')?.lang).toBe('fil')
  expect(levelFromLine(en, 'landmark')).toBeUndefined()
  expect(levelFromLine(en, undefined)).toBeUndefined()
  expect(levelFromLine(en)).toBeUndefined()
  expect(levelFromLine(en, 'rubbish')).toBeUndefined()
  expect(levelFromLine(en, 'constructor')).toBeUndefined()
})

it('every landmark has a line in both tables', () => {
  for (const landmark of LANDMARKS) {
    const key = `result.landmark.${landmark}`
    expect(Object.hasOwn(EN, key), `en ${key}`).toBe(true)
    expect(Object.hasOwn(FIL, key), `fil ${key}`).toBe(true)
    expect(landmarkLine(en, landmark)?.lang, key).toBe('en')
    expect(landmarkLine(fil, landmark)?.lang, key).toBe('fil')
  }
  expect(LANDMARKS).toHaveLength(15)
})

it('a landmark line names its reference: a parked car for wheels and bodies, an adult in the photo for people', () => {
  for (const landmark of [...WHEEL_LANDMARKS, ...BODY_FLOORS]) {
    expect(landmarkLine(en, landmark)?.text, landmark).toContain('a parked car')
    expect(landmarkLine(fil, landmark)?.text, landmark).toContain('nakaparadang sasakyan')
  }
  for (const landmark of PEOPLE_LANDMARKS) {
    expect(landmarkLine(en, landmark)?.text, landmark).toContain('an adult in the photo')
    expect(landmarkLine(fil, landmark)?.text, landmark).toContain('adult sa photo')
  }
})

it("a landmark line is the spec's own wording, ends with a full stop, and no two are alike", () => {
  expect(landmarkLine(en, 'rim_three_quarters')?.text).toBe(
    "Water reaches three quarters of the way up a parked car's wheel rim.",
  )
  const lines = LANDMARKS.map((landmark) => landmarkLine(en, landmark)?.text ?? '')
  expect(new Set(lines).size).toBe(lines.length)
  for (const line of lines) expect(line).toMatch(/^Water (reaches|covers)\b.*\.$/)
})

it('a category that reads no level, or one the app has never heard of, has no landmark line', () => {
  const words = ['not_visible', 'below_bumper', 'bumper', 'door_sill', '', 'water', 'constructor', '__proto__', 'toString']
  for (const word of words) {
    expect(landmarkLine(en, word), word).toBeUndefined()
    expect(landmarkLine(fil, word), word).toBeUndefined()
  }
})

it('every refusal and failure reason has a line in both tables, and none shows its code', () => {
  expect(REASONS).toHaveLength(14)
  for (const reason of REASONS) {
    const key = `reason.${reason}`
    expect(Object.hasOwn(EN, key), `en ${key}`).toBe(true)
    expect(Object.hasOwn(FIL, key), `fil ${key}`).toBe(true)
    const line = reasonLine(en, reason)
    expect(line.lang).toBe('en')
    expect(line.text, reason).toMatch(/^[A-Z].*\.$/)
    expect(line.text, reason).not.toContain(reason)
    expect(line.text, reason).not.toMatch(/_/)
    expect(reasonLine(fil, reason).text.length).toBeGreaterThan(0)
  }
})

it('the two reason lines the spec quotes are its own words', () => {
  expect(reasonLine(en, 'too_dark').text).toBe('The photo is too dark to read.')
  expect(reasonLine(en, 'references_disagree').text).toBe(
    'The cars and people in the photo give depths more than one level apart.',
  )
})

it('a reason the app does not know gets a plain line, never the raw code', () => {
  const fallback = reasonLine(en, 'some_new_code')
  expect(fallback).toEqual(en('reason.other'))
  expect(fallback.text).not.toContain('some_new_code')
  for (const word of ['', 'constructor', '__proto__', 'toString', 'hasOwnProperty']) {
    expect(reasonLine(en, word), word).toEqual(en('reason.other'))
  }
})

it('a reason line stays English on a Taglish screen until its Taglish is reviewed', () => {
  for (const reason of REASONS) {
    expect(FIL[`reason.${reason}`].reviewed, reason).toBe(false)
    expect(reasonLine(fil, reason).lang, reason).toBe('en')
    expect(reasonLine(fil, reason).text, reason).toBe(reasonLine(en, reason).text)
  }
  expect(reasonLine(fil, 'something_else').lang).toBe('en')
})

it('the result and reason lines say nothing about a road or a route, and tell no one to go near water or traffic', () => {
  for (const table of [EN, FIL]) {
    for (const key of resultAndReasonKeys(table)) {
      const { text } = (table as Record<string, { text: string }>)[key]
      expect(text, key).not.toMatch(WHOLE_ROAD)
      expect(text, key).not.toMatch(APPROACH)
    }
  }
})

it("no result or reason line counts the levels as MMDA's own", () => {
  for (const table of [EN, FIL]) {
    for (const key of resultAndReasonKeys(table)) {
      const { text } = (table as Record<string, { text: string }>)[key]
      expect(text, key).not.toMatch(/MMDA(['’]?s)? (9|nine)|(9|nine) levels/i)
    }
  }
})

it('the outcome lines say what spec §4.2 says', () => {
  expect(en('result.noFlood').text).toBe('No flood seen at this spot.')
  expect(en('result.failed').text).toBe('Processing failed, try again.')
  expect(en('result.private').text).toBe("Taken outside Metro Manila, so only you see this result. It isn't on the map.")
  expect(en('result.noResult').text).toBe('No result yet. The analysis is taking longer than usual.')
  expect(en('result.checkAgain').text).toBe('Check again')
  expect(en('result.tryAgain').text).toBe('Try again')
})

it('the three outcomes keep their own lines: no flood, processing failed, and can\'t tell', () => {
  const noFlood = en('result.noFlood').text
  const failed = en('result.failed').text
  const cantTell = en('refusal.d19').text
  expect(new Set([noFlood, failed, cantTell]).size).toBe(3)
  expect(failed).not.toMatch(/flood seen|can't tell/i)
  expect(noFlood).toContain('at this spot')
  expect(noFlood).not.toMatch(/failed|can't tell/i)
})

it("C81's English lines and D19's start reviewed; every other new line and every Taglish draft doesn't", () => {
  // The pattern, the four level names and the three class lines C81 spells out. Its PATV and NPATV lines come
  // from plan §9, Table 10, not from C81, so they wait for Rene's review like the other names.
  const c81 = new Set([
    'result.level.exact',
    'result.level.floor',
    'result.level.off',
    'result.levelName.below_gutter',
    'result.levelName.knee',
    'result.levelName.tire',
    'result.levelName.above_chest',
    'result.class.nplv',
    'result.class.belowGutter',
    'result.class.aboveChest',
  ])
  expect(EN['refusal.d19'].reviewed).toBe(true)
  expect(FIL['refusal.d19'].reviewed).toBe(false)
  const keys = resultAndReasonKeys(EN)
  for (const key of keys) {
    expect(EN[key as keyof typeof EN].reviewed, `en ${key}`).toBe(c81.has(key))
    expect(FIL[key as keyof typeof FIL].reviewed, `fil ${key}`).toBe(false)
  }
  for (const key of c81) expect(keys, key).toContain(key)
})

it('the two tables hold the same keys', () => {
  expect(Object.keys(FIL).sort()).toEqual(Object.keys(EN).sort())
})

// The line for a reference the reading left out (amendment 2). It names the cause in plain words, and a cause the
// app doesn't know gets a general line, never the code.
it('every drop cause has a line in both tables, starting "Not used", and none shows its code', () => {
  for (const cause of DROP_CAUSES) {
    const key = `dropped.${cause}`
    expect(Object.hasOwn(EN, key), `en ${key}`).toBe(true)
    expect(Object.hasOwn(FIL, key), `fil ${key}`).toBe(true)
    const line = dropLine(en, cause)
    expect(line.lang).toBe('en')
    expect(line.text, cause).toMatch(/^Not used\b.*\.$/)
    expect(line.text, cause).not.toMatch(/_/)
    expect(dropLine(fil, cause).lang).toBe('fil')
    expect(dropLine(fil, cause).text, cause).toMatch(/^Hindi ginamit\b.*\.$/)
  }
  expect(dropLine(en, 'person_not_adult').text).toBe('Not used, since this person may not be an adult.')
  expect(dropLine(en, 'vehicle_moving').text).toBe('Not used, since the vehicle may be moving.')
})

it('a drop cause the app does not know gets "Not used for this reading.", never the raw code', () => {
  for (const word of ['a_new_cause', '', 'constructor', '__proto__', 'toString']) {
    expect(dropLine(en, word), word).toEqual(en('dropped.other'))
  }
  expect(en('dropped.other').text).toBe('Not used for this reading.')
  expect(dropLine(en, 'a_new_cause').text).not.toContain('a_new_cause')
})

it('a drop line speaks of no road, route or approach, and no level or class', () => {
  for (const table of [EN, FIL]) {
    for (const key of Object.keys(table).filter((name) => name.startsWith('dropped.'))) {
      const { text } = (table as Record<string, { text: string }>)[key]
      expect(text, key).not.toMatch(WHOLE_ROAD)
      expect(text, key).not.toMatch(APPROACH)
      expect(text, key).not.toMatch(/\b(PATV|NPLV|NPATV|MMDA)\b/)
    }
  }
})

it('the drop lines are new lines, so they wait for review in both tables', () => {
  for (const key of [...DROP_CAUSES.map((cause) => `dropped.${cause}`), 'dropped.other'] as const) {
    expect(EN[key as keyof typeof EN].reviewed, `en ${key}`).toBe(false)
    expect(FIL[key as keyof typeof FIL].reviewed, `fil ${key}`).toBe(false)
  }
})

it('a reference line is its drop cause when it was dropped, else where the water meets it, else nothing', () => {
  expect(referenceLine(en, { dropped: 'person_not_adult', landmark: null })).toEqual(dropLine(en, 'person_not_adult'))
  // A dropped reference has no level, and whatever landmark it holds is not shown: the cause is.
  expect(referenceLine(en, { dropped: 'vehicle_moving', landmark: 'hub' })).toEqual(dropLine(en, 'vehicle_moving'))
  expect(referenceLine(en, { dropped: null, landmark: 'hub' })).toEqual(landmarkLine(en, 'hub'))
  expect(referenceLine(en, { dropped: null, landmark: null })).toBeUndefined()
  expect(referenceLine(en, { dropped: null, landmark: 'not_a_landmark' })).toBeUndefined()
})
