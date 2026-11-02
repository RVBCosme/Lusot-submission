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
  depthLine,
  dropLine,
  inchesLine,
  landmarkLine,
  levelFromLine,
  levelLine,
  reasonLine,
  referenceLine,
  verdictLines,
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
  expect(inchesLine(en, 15, 18).text).toBe('Estimated 15 to 18 in (0.38 to 0.46 m).')
  expect(reasonLine(makeT('fil'), 'too_dark').lang).toBe('fil') // reviewed in M20
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
  expect(inchesLine(en, 14.9, 18.2).text).toBe('Estimated 14.9 to 18.2 in (0.38 to 0.46 m).')
  expect(inchesLine(en, 15, 15).text).toBe('Estimated 15 in (0.38 m).')
  expect(inchesLine(fil, 15, 18).text).toBe('Tinatayang 15 hanggang 18 in (0.38 hanggang 0.46 m).')
  expect(inchesLine(fil, 15, 15).text).toBe('Tinatayang 15 in (0.38 m).')
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

it('a reason line shows in Taglish once its Taglish is reviewed, and stays English until then', () => {
  for (const reason of REASONS) {
    const line = FIL[`reason.${reason}`]
    expect(line.reviewed, reason).toBe(true) // M20
    expect(reasonLine(fil, reason), reason).toEqual({ text: line.text, lang: 'fil' })
  }
  expect(reasonLine(fil, 'something_else')).toEqual({ text: FIL['reason.other'].text, lang: 'fil' })

  // A reason line whose Taglish isn't reviewed, such as a new one, stays English.
  const reviewed = FIL['reason.too_dark']
  FIL['reason.too_dark'] = { ...reviewed, reviewed: false }
  try {
    expect(reasonLine(fil, 'too_dark')).toEqual({ text: EN['reason.too_dark'].text, lang: 'en' })
  } finally {
    FIL['reason.too_dark'] = reviewed
  }
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

it("D19's two lines and every result and reason line, English and Taglish, passed the M20 review", () => {
  // C81's English lines and D19's start reviewed. The rest of C81's table (the other level names, the PATV and
  // NPATV lines from plan §9, Table 10, and every Taglish line) joined them in the M20 review of Oct 30.
  expect(EN['refusal.d19'].reviewed).toBe(true)
  expect(FIL['refusal.d19'].reviewed).toBe(true)
  const keys = resultAndReasonKeys(EN)
  expect(keys.length).toBeGreaterThan(50)
  for (const key of keys) {
    expect(EN[key as keyof typeof EN].reviewed, `en ${key}`).toBe(true)
    expect(FIL[key as keyof typeof FIL].reviewed, `fil ${key}`).toBe(true)
  }
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

it('the drop lines passed the M20 review in both tables', () => {
  for (const key of [...DROP_CAUSES.map((cause) => `dropped.${cause}`), 'dropped.other'] as const) {
    expect(EN[key as keyof typeof EN].reviewed, `en ${key}`).toBe(true)
    expect(FIL[key as keyof typeof FIL].reviewed, `fil ${key}`).toBe(true)
  }
})

it("C92's small-person line is its own, as the tracker approved it at M20 (Nov 2)", () => {
  expect(EN['dropped.person_small'].text).toBe('Not used, since this person is too small in the photo to read.')
  expect(FIL['dropped.person_small'].text).toBe('Hindi ginamit, dahil masyadong maliit ang taong ito sa photo para mabasa.')
  expect(EN['dropped.person_small'].text).not.toBe(EN['dropped.person_no_reading'].text)
})

it('a reference line is its drop cause when it was dropped, else where the water meets it, else nothing', () => {
  expect(referenceLine(en, { dropped: 'person_not_adult', landmark: null })).toEqual(dropLine(en, 'person_not_adult'))
  // A dropped reference has no level, and whatever landmark it holds is not shown: the cause is.
  expect(referenceLine(en, { dropped: 'vehicle_moving', landmark: 'hub' })).toEqual(dropLine(en, 'vehicle_moving'))
  expect(referenceLine(en, { dropped: null, landmark: 'hub' })).toEqual(landmarkLine(en, 'hub'))
  expect(referenceLine(en, { dropped: null, landmark: null })).toBeUndefined()
  expect(referenceLine(en, { dropped: null, landmark: 'not_a_landmark' })).toBeUndefined()
})

// Rene's rule of Nov 2 (C639): the headline of a level result is a verdict at this spot, named as MMDA's class for the
// level, and the level's depth range in metres goes with it.
const VERDICTS = {
  PATV: 'Verdict at this spot: Passable to all vehicles',
  NPLV: 'Verdict at this spot: Not passable to light vehicles',
  NPATV: 'Verdict at this spot: Not passable to any vehicle',
} as const

it("the verdict is the level's own class, in MMDA's three classes, with a sub-line naming where it comes from", () => {
  for (const level of LEVELS) {
    const { verdict, sub } = verdictLines(en, level, false)
    expect(verdict?.text, level).toBe(VERDICTS[PASSABILITY[level]])
    // The seven gauge levels say whose class it is; the two added levels name the MMDA level they lie beyond.
    const name = en(`result.levelName.${level}`).text
    expect(sub?.text, level).toBe(OFF_GAUGE.includes(level) ? classLine(en, level).text : `MMDA's class for the ${name} level.`)
  }
  expect(verdictLines(en, 'knee', false).sub?.text).toBe("MMDA's class for the knee level.")
  expect(verdictLines(en, 'half_knee', false).sub?.text).toBe("MMDA's class for the half-knee level.")
  expect(verdictLines(en, 'below_gutter', false).sub?.text).toBe(
    "Shallower than MMDA's gutter level, which MMDA lists as passable to all vehicles (PATV).",
  )
  expect(verdictLines(en, 'above_chest', false).sub?.text).toBe(
    "Deeper than MMDA's chest level, which MMDA lists as not passable to any vehicle (NPATV).",
  )
})

// A floor is "at least" a level, so the water may be deeper. Deeper only makes an NPLV or NPATV class worse, so those keep
// their verdict; a PATV floor could really be a deeper level in another class, so it never says "Passable".
it('a floor whose class is NPLV keeps its verdict', () => {
  expect(verdictLines(en, 'knee', true).verdict?.text).toBe(VERDICTS.NPLV)
  expect(verdictLines(en, 'half_tire', true).verdict?.text).toBe(VERDICTS.NPLV)
  expect(verdictLines(en, 'knee', true).sub?.text).toBe("MMDA's class for the knee level.")
})

it('a floor whose class is NPATV keeps its verdict', () => {
  expect(verdictLines(en, 'tire', true).verdict?.text).toBe(VERDICTS.NPATV)
  expect(verdictLines(en, 'tire', true).sub?.text).toBe("MMDA's class for the tire level.")
  expect(verdictLines(en, 'above_chest', true).verdict?.text).toBe(VERDICTS.NPATV)
  expect(verdictLines(fil, 'tire', true).verdict?.text).toBe('Verdict sa spot na ito: Hindi passable sa anumang sasakyan')
})

it('a floor whose class is PATV gets "No verdict: the water may be deeper", never "Passable", and no class sub-line', () => {
  const patv = LEVELS.filter((level) => PASSABILITY[level] === 'PATV')
  expect(patv).toEqual(['below_gutter', 'gutter', 'half_knee'])
  for (const level of patv) {
    const name = en(`result.levelName.${level}`).text
    const lines = verdictLines(en, level, true)
    expect(lines.verdict?.text, level).toBe(`No verdict: the water may be deeper than the ${name} level.`)
    expect(lines.sub, level).toBeUndefined()
    const filLines = verdictLines(fil, level, true)
    expect(filLines.verdict?.text, level).toMatch(/^Walang verdict: maaaring mas malalim ang tubig kaysa sa .+ level\.$/)
    expect(filLines.sub, level).toBeUndefined()
    // No line the floor shows, in either language, calls the spot passable.
    for (const [, t] of BOTH) {
      const shown = [verdictLines(t, level, true).verdict?.text, depthLine(t, level, true).text].join(' ')
      expect(shown, level).not.toMatch(/passable/i)
    }
  }
  expect(verdictLines(en, 'gutter', true).verdict?.text).toBe('No verdict: the water may be deeper than the gutter level.')
  expect(verdictLines(fil, 'half_knee', true).verdict?.text).toBe('Walang verdict: maaaring mas malalim ang tubig kaysa sa half-knee level.')
})

it('"Passable to all vehicles" is said only for a PATV level that is not a floor, in both languages', () => {
  for (const [lang, t] of BOTH) {
    const passable = lang === 'en' ? 'Verdict at this spot: Passable' : 'Verdict sa spot na ito: Passable'
    for (const level of LEVELS) {
      for (const floor of [false, true]) {
        const says = (verdictLines(t, level, floor).verdict?.text ?? '').startsWith(passable)
        expect(says, `${lang} ${level} ${floor}`).toBe(PASSABILITY[level] === 'PATV' && !floor)
      }
    }
  }
})

it('the verdict reads in Taglish with the same class, and every verdict is for this spot or says there is none', () => {
  expect(verdictLines(fil, 'knee', false).verdict?.text).toBe('Verdict sa spot na ito: Hindi passable sa light vehicles')
  expect(verdictLines(fil, 'gutter', false).verdict?.text).toBe('Verdict sa spot na ito: Passable sa lahat ng sasakyan')
  expect(verdictLines(fil, 'chest', false).verdict?.text).toBe('Verdict sa spot na ito: Hindi passable sa anumang sasakyan')
  expect(verdictLines(fil, 'knee', false).sub?.text).toBe('Ang class ng MMDA para sa knee level.')
  expect(en('verdict.none').text).toBe("No verdict: Lusot can't tell from this photo.")
  expect(fil('verdict.none').text).toBe('Walang verdict: hindi masabi ng Lusot mula sa photo na ito.')
  for (const [lang, t] of BOTH) {
    for (const level of LEVELS) {
      for (const floor of [false, true]) {
        const { verdict, sub } = verdictLines(t, level, floor)
        expect(verdict?.lang, `${lang} ${level}`).toBe(lang)
        const spot = lang === 'en' ? /^(Verdict at this spot|No verdict)/ : /^(Verdict sa spot na ito|Walang verdict)/
        expect(verdict?.text, `${lang} ${level}`).toMatch(spot)
        for (const line of [verdict, sub]) expect(line?.text ?? '', `${lang} ${level}`).not.toMatch(/\{\w+\}/)
      }
    }
  }
})

// The nine depth lines, level by level: the level's limits in inches (eval/rules.md) and the same limits in metres.
it('the depth line of each of the 9 levels is pinned, with its limits in metres and inches', () => {
  expect(LEVELS.map((level) => depthLine(en, level, false).text)).toEqual([
    'Depth: below gutter level, up to 0.13 m (5 in).',
    'Depth: gutter level, about 0.13 to 0.20 m (5 to 8 in).',
    'Depth: half-knee level, about 0.20 to 0.25 m (8 to 10 in).',
    'Depth: half-tire level, about 0.25 to 0.33 m (10 to 13 in).',
    'Depth: knee level, about 0.33 to 0.48 m (13 to 19 in).',
    'Depth: tire level, about 0.48 to 0.66 m (19 to 26 in).',
    'Depth: waist level, about 0.66 to 0.94 m (26 to 37 in).',
    'Depth: chest level, about 0.94 to 1.14 m (37 to 45 in).',
    'Depth: above chest level, over 1.14 m (45 in).',
  ])
})

it('a floor reads "or deeper, at least" its lower limit, and a floor on the first level gives no metres', () => {
  expect(depthLine(en, 'knee', true).text).toBe('Depth: knee level or deeper, at least 0.33 m (13 in).')
  expect(depthLine(en, 'tire', true).text).toBe('Depth: tire level or deeper, at least 0.48 m (19 in).')
  expect(depthLine(en, 'gutter', true).text).toBe('Depth: gutter level or deeper, at least 0.13 m (5 in).')
  expect(depthLine(en, 'above_chest', true).text).toBe('Depth: above chest level or deeper, at least 1.14 m (45 in).')
  expect(depthLine(en, 'below_gutter', true).text).toBe('Depth: below gutter level or deeper.')
  expect(depthLine(fil, 'below_gutter', true).text).toBe('Lalim: mas mababa sa gutter level o mas malalim.')
})

it('the depth line reads in Taglish, with the same numbers', () => {
  expect(depthLine(fil, 'knee', false).text).toBe('Lalim: knee level, mga 0.33 hanggang 0.48 m (13 hanggang 19 in).')
  expect(depthLine(fil, 'below_gutter', false).text).toBe('Lalim: mas mababa sa gutter level, hanggang 0.13 m (5 in).')
  expect(depthLine(fil, 'above_chest', false).text).toBe('Lalim: lampas chest level, lampas 1.14 m (45 in).')
  expect(depthLine(fil, 'tire', true).text).toBe('Lalim: tire level o mas malalim, hindi bababa sa 0.48 m (19 in).')
  for (const [lang, t] of BOTH) {
    for (const level of LEVELS) {
      for (const floor of [false, true]) {
        const line = depthLine(t, level, floor)
        expect(line.lang, `${lang} ${level}`).toBe(lang)
        expect(line.text, `${lang} ${level}`).not.toMatch(/\{\w+\}|undefined|NaN/)
      }
    }
  }
})

// The verdict and depth keys sit outside result. and reason., so the sweeps above over those prefixes don't reach them.
// They hold the same rules: no banned word, no road or route, nothing about what a person may do, and Rene's review.
it('the verdict and depth lines are in both tables, reviewed, and break none of the copy rules', () => {
  const keys = Object.keys(EN).filter((key) => key.startsWith('verdict.') || key.startsWith('depth.'))
  expect(keys.sort()).toEqual(
    [
      'depth.floor',
      'depth.floorNoMetres',
      'depth.over',
      'depth.range',
      'depth.upTo',
      'verdict.classOf',
      'verdict.mayBeDeeper',
      'verdict.none',
      'verdict.nplv',
      'verdict.npatv',
      'verdict.patv',
    ].sort(),
  )
  for (const table of [EN, FIL]) {
    for (const key of keys) {
      const entry = (table as Record<string, { text: string; reviewed: boolean }>)[key]
      expect(entry, key).toBeDefined()
      expect(entry.reviewed, key).toBe(true)
      expect(entry.text, key).not.toMatch(/safe|ligtas/i)
      expect(entry.text, key).not.toMatch(WHOLE_ROAD)
      expect(entry.text, key).not.toMatch(APPROACH)
      expect(entry.text, key).not.toMatch(/\bcross|tawid|go through/i)
      expect(entry.text, key).not.toMatch(/MMDA(['’]?s)? (9|nine)|(9|nine) levels/i)
    }
  }
})

it("the inches line adds metres computed from the inches it shows, never from the level's limits", () => {
  expect(inchesLine(en, 20, 24).text).toBe('Estimated 20 to 24 in (0.51 to 0.61 m).')
  expect(inchesLine(en, 6.5, 6.5).text).toBe('Estimated 6.5 in (0.17 m).')
  expect(inchesLine(fil, 20, 24).text).toBe('Tinatayang 20 hanggang 24 in (0.51 hanggang 0.61 m).')
})
