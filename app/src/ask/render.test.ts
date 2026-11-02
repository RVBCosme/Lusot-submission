import { describe, expect, it } from 'vitest'
import { makeT } from '../i18n'
import { EN, type Entry } from '../i18n/en'
import { FIL } from '../i18n/fil'
import type { AskAnswer, AskReport } from '../lib/api'
import { type AnswerLine, maskBannedWords, renderAnswer } from './render'

const NOW = new Date('2026-10-30T10:30:00Z')
const en = makeT('en')
const fil = makeT('fil')
const SPOT = 'España Blvd cor. Maceda St'

// MS5's patterns (i18n.test.tsx, C608): the banned words anywhere in a word, and the crossing phrases.
const BANNED_WORDS = /safe|ligtas/i
const CROSSING = /you can cross|you can pass|go ahead|pu?wedeng dumaan|tumawid ka|lusutan mo/i
const AT_THIS_SPOT = /at this spot|sa spot na ito/

let n = 0
function report(over: Partial<AskReport> = {}): AskReport {
  n += 1
  return {
    id: `r_${n.toString(16).padStart(32, '0')}`,
    lat: 14.6095,
    lng: 120.9894,
    capturedAt: '2026-10-30T10:05:00Z', // 25 min before NOW
    mode: 'live',
    flags: 0,
    gpsAccuracyM: 12,
    level: 'knee',
    landmark: 'rim_three_quarters',
    passability: 'NPLV',
    levelIsFloor: false,
    basis: { vehicles: 1, people: 0 },
    distanceM: 120,
    ...over,
  }
}

const DEEP = report({ level: 'waist', passability: 'NPATV' })
const MID = report({ level: 'knee', distanceM: 40, capturedAt: '2026-10-30T09:30:00Z' })
const SHALLOW = report({ level: 'gutter', passability: 'PATV', distanceM: 250 })
const DEMO = report({
  mode: 'demo',
  capturedAt: '2009-09-26T01:30:00Z',
  gpsAccuracyM: null,
  level: 'above_chest',
  passability: 'NPATV',
  credit: 'Photo: Example Contributor (mock), CC BY 4.0, faces and plates blurred by Lusot',
  place: 'Marikina',
  event: 'Typhoon Ondoy',
  distanceM: 210,
})

function answer(over: Partial<AskAnswer> = {}): AskAnswer {
  return {
    source: 'model',
    fallback: null,
    kind: 'reports',
    crossing: false,
    vehicle: null,
    place: { name: SPOT, source: 'spots' },
    windowMin: 180,
    radiusM: 300,
    count: 3,
    reports: [DEEP, MID, SHALLOW],
    demo: [DEMO],
    deepestId: DEEP.id,
    cited: [DEEP.id, MID.id],
    suggestions: [],
    ...over,
  }
}

const EMPTY = { reports: [], demo: [], count: 0, deepestId: null, cited: [] }
const keys = (lines: AnswerLine[]) => lines.map((line) => line.key)
const texts = (lines: AnswerLine[]) => lines.map((line) => line.text.text)

// Puts `entry` in a string table for the length of `run`, then restores the table as it was.
function withEntry(table: Record<string, Entry>, key: string, entry: Entry, run: () => void) {
  const original = table[key]
  table[key] = entry
  try {
    run()
  } finally {
    table[key] = original
  }
}

const DEMO_CARD = ['ask.answer.demo', 'level', 'sample.photoFrom', 'credit']

describe('renderAnswer, one test per kind', () => {
  it('reports: the crossing line first, the summary, the deepest card, the vehicle line, the other cards, the demo cards', () => {
    const lines = renderAnswer(answer({ crossing: true, vehicle: 'light' }), en, NOW)

    expect(keys(lines)).toEqual([
      'ask.answer.crossing',
      'ask.answer.summaryMany',
      'level',
      'class',
      'ask.answer.where',
      'ask.answer.vehicleLight',
      'level',
      'ask.answer.where',
      'level',
      'ask.answer.where',
      ...DEMO_CARD,
    ])
    expect(lines[0]).toMatchObject({ part: 'crossing', text: { text: "I can't tell you whether to cross or go through." } })
    expect(lines[1]).toMatchObject({
      part: 'summary',
      text: { text: `3 reports within 300 m of ${SPOT} in the last 3 hours.`, lang: 'en' },
    })
    expect(texts(lines).slice(2, 4)).toEqual([
      'Waist deep at this spot (MMDA level).',
      'MMDA lists this level as not passable to any vehicle (NPATV).',
    ])
    // The cards carry their report's id, and the cited ones are marked used.
    const byReport = (id: string) => lines.filter((line) => line.reportId === id)
    expect(byReport(DEEP.id).every((line) => line.part === 'card' && line.used === true)).toBe(true)
    expect(byReport(MID.id).every((line) => line.used === true)).toBe(true)
    expect(byReport(SHALLOW.id).every((line) => line.used === false)).toBe(true)
    expect(byReport(DEMO.id).every((line) => line.demo === true && line.used === false)).toBe(true)
    expect(lines.find((line) => line.key === 'credit')?.text).toEqual({ text: DEMO.credit, lang: 'en' })
    expect(lines.find((line) => line.key === 'sample.photoFrom')?.text.text).toBe(
      'Photo from Sep 26, 2009, Marikina, Typhoon Ondoy',
    )
  })

  it('one report reads "1 report"', () => {
    const lines = renderAnswer(answer({ reports: [DEEP], demo: [], count: 1, cited: [] }), en, NOW)

    expect(keys(lines)).toEqual(['ask.answer.summaryOne', 'level', 'class', 'ask.answer.where'])
    expect(lines[0].text.text).toBe(`1 report within 300 m of ${SPOT} in the last 3 hours.`)
  })

  it('no_reports: its line, the note, then a demo card', () => {
    const lines = renderAnswer(answer({ kind: 'no_reports', ...EMPTY, demo: [DEMO] }), en, NOW)

    expect(keys(lines)).toEqual(['ask.answer.noReports', 'ask.answer.noReportNote', ...DEMO_CARD])
    expect(texts(lines).slice(0, 2)).toEqual([
      `No recent reports within 300 m of ${SPOT} in the last 3 hours.`,
      "No report doesn't mean no flood.",
    ])
  })

  it.each([
    ['no_place', 'ask.answer.noPlace'],
    ['lookup_unavailable', 'ask.answer.lookupUnavailable'],
    ['outside_metro_manila', 'ask.answer.outside'],
    ['no_location', 'ask.answer.noLocation'],
    ['off_topic', 'ask.answer.offTopic'],
    ['no_speech', 'ask.answer.noSpeech'],
  ] as const)('%s shows its one line', (kind, key) => {
    const lines = renderAnswer(answer({ kind, place: null, ...EMPTY }), en, NOW)

    expect(keys(lines)).toEqual([key])
    expect(lines[0].text).toEqual({ text: EN[key].text, lang: 'en' })
  })

  it("lookup_unavailable shows its own line, not the no-place line", () => {
    const lines = renderAnswer(answer({ kind: 'lookup_unavailable', place: null, ...EMPTY }), en, NOW)

    expect(texts(lines)).toEqual(['I couldn\'t look up that place just now. Try again in a minute, or name a nearby landmark.'])
    expect(keys(lines)).not.toContain('ask.answer.noPlace')
  })

  it('place_too_broad shows its line, then one suggestion per spot', () => {
    const suggestions = ['Taft Ave in front of PGH', 'Taft Ave cor. Quirino Ave']
    const lines = renderAnswer(answer({ kind: 'place_too_broad', place: null, ...EMPTY, suggestions }), en, NOW)

    expect(keys(lines)).toEqual(['ask.answer.tooBroad', 'ask.ui.suggestionQuestion', 'ask.ui.suggestionQuestion'])
    expect(lines.slice(1)).toEqual([
      expect.objectContaining({ part: 'suggestion', spot: suggestions[0], text: { text: `How deep is it at ${suggestions[0]}?`, lang: 'en' } }),
      expect.objectContaining({ part: 'suggestion', spot: suggestions[1] }),
    ])
  })

  it('a crossing reading puts its line first on any kind', () => {
    const lines = renderAnswer(answer({ kind: 'no_place', crossing: true, place: null, ...EMPTY }), en, NOW)

    expect(keys(lines)).toEqual(['ask.answer.crossing', 'ask.answer.noPlace'])
  })
})

describe('renderAnswer, the vehicle and the cards', () => {
  it('on foot drops every class line and adds the on-foot line', () => {
    const lines = renderAnswer(answer({ vehicle: 'on_foot' }), en, NOW)

    expect(keys(lines)).not.toContain('class')
    expect(keys(lines).slice(0, 5)).toEqual(['ask.answer.summaryMany', 'level', 'ask.answer.where', 'ask.answer.onFoot', 'level'])
    expect(texts(lines)).toContain("MMDA's classes are for vehicles, so this answer gives the level only.")
  })

  it('heavy shows the crossing line directly under the class line (AskL-Q10)', () => {
    const lines = renderAnswer(answer({ vehicle: 'heavy' }), en, NOW)

    expect(keys(lines).slice(0, 6)).toEqual([
      'ask.answer.summaryMany',
      'level',
      'class',
      'ask.answer.crossing',
      'ask.answer.where',
      'ask.answer.vehicleHeavy',
    ])
    // It belongs to the deepest card, so a screen that groups lines by part keeps it under the class line.
    expect(lines[3]).toMatchObject({ part: 'card', reportId: DEEP.id })
    // With the crossing reading too, the line shows first and again under the class line.
    const crossing = renderAnswer(answer({ vehicle: 'heavy', crossing: true }), en, NOW)
    expect(keys(crossing).slice(0, 5)).toEqual(['ask.answer.crossing', 'ask.answer.summaryMany', 'level', 'class', 'ask.answer.crossing'])
  })

  it('no vehicle named gives no vehicle line, and keeps the class line', () => {
    const lines = renderAnswer(answer({ vehicle: null }), en, NOW)

    expect(keys(lines).slice(0, 5)).toEqual(['ask.answer.summaryMany', 'level', 'class', 'ask.answer.where', 'level'])
  })

  it('the where line reads "Photo taken 25 min ago, 120 m from …", with no "ago ago"', () => {
    const lines = renderAnswer(answer(), en, NOW)
    const where = lines.filter((line) => line.key === 'ask.answer.where').map((line) => line.text.text)

    expect(where[0]).toBe(`Photo taken 25 min ago, 120 m from ${SPOT}.`)
    expect(where[1]).toBe(`Photo taken 1 h ago, 40 m from ${SPOT}.`)
    for (const text of where) expect(text).not.toMatch(/ago ago/)
  })

  it('a floor reads "At least"', () => {
    const lines = renderAnswer(answer({ reports: [{ ...DEEP, levelIsFloor: true }], demo: [], count: 1 }), en, NOW)

    expect(lines[1].text.text).toBe('At least waist deep at this spot (MMDA level).')
  })

  // The result card's rule (the tracker, Nov 2): a floor is "at least" a level, so only an NPATV floor keeps its class. A
  // PATV or NPLV floor could be a deeper level in a worse class, and MMDA's class for the floor would read as a verdict.
  it('a floor whose class is PATV or NPLV gets no class line, and an NPATV floor keeps it', () => {
    const floor = (over: Partial<AskReport>) => {
      const deepest = report({ levelIsFloor: true, ...over })
      return renderAnswer(answer({ reports: [deepest], demo: [], count: 1, deepestId: deepest.id }), en, NOW)
    }
    for (const [level, passability] of [['gutter', 'PATV'], ['knee', 'NPLV'], ['below_gutter', 'PATV']] as const) {
      const lines = floor({ level, passability })
      expect(keys(lines), level).toEqual(['ask.answer.summaryOne', 'level', 'ask.answer.where'])
    }
    for (const level of ['tire', 'above_chest'] as const) {
      expect(keys(floor({ level, passability: 'NPATV' })), level).toEqual(['ask.answer.summaryOne', 'level', 'class', 'ask.answer.where'])
    }
    // An exact reading of the same levels keeps its class line.
    const exact = report({ level: 'knee', passability: 'NPLV' })
    expect(keys(renderAnswer(answer({ reports: [exact], demo: [], count: 1, deepestId: exact.id }), en, NOW))).toContain('class')
  })

  it('a heavy vehicle keeps the crossing line (AskL-Q10) under the level line when the floor gives no class line', () => {
    const deepest = report({ level: 'knee', passability: 'NPLV', levelIsFloor: true })
    const lines = renderAnswer(answer({ vehicle: 'heavy', reports: [deepest], demo: [], count: 1, deepestId: deepest.id }), en, NOW)

    expect(keys(lines).slice(0, 5)).toEqual(['ask.answer.summaryOne', 'level', 'ask.answer.crossing', 'ask.answer.where', 'ask.answer.vehicleHeavy'])
    expect(lines[2]).toMatchObject({ part: 'card', reportId: deepest.id })
  })

  it('an answer without citations has no used marks', () => {
    const lines = renderAnswer(answer({ cited: [] }), en, NOW)

    expect(lines.some((line) => line.used === true)).toBe(false)
  })

  it('the plain list adds its note and has no vehicle line or used marks', () => {
    const plain = answer({ source: 'plain_list', fallback: 'model_calls_paused', vehicle: null, cited: [] })
    const lines = renderAnswer(plain, en, NOW)

    expect(keys(lines).slice(0, 2)).toEqual(['ask.answer.plainList', 'ask.answer.summaryMany'])
    expect(keys(lines).filter((key) => key.startsWith('ask.answer.vehicle'))).toEqual([])
    expect(lines.some((line) => line.used === true)).toBe(false)
    // The plain list keeps the crossing words' line, ahead of its note.
    expect(keys(renderAnswer({ ...plain, crossing: true }, en, NOW)).slice(0, 2)).toEqual(['ask.answer.crossing', 'ask.answer.plainList'])
  })

  it('the plain list\'s note shows only with a list: a plain-list no_place has its one line', () => {
    const lines = renderAnswer(answer({ source: 'plain_list', fallback: 'deadline', kind: 'no_place', place: null, ...EMPTY }), en, NOW)

    expect(keys(lines)).toEqual(['ask.answer.noPlace'])
  })

  it('the vehicle and on-foot lines explain report cards, so a no_reports answer has neither', () => {
    for (const vehicle of ['light', 'heavy', 'on_foot'] as const) {
      const lines = renderAnswer(answer({ kind: 'no_reports', ...EMPTY, demo: [DEMO], vehicle }), en, NOW)
      expect(keys(lines), vehicle).toEqual(['ask.answer.noReports', 'ask.answer.noReportNote', ...DEMO_CARD])
    }
  })

  it('a demo pin without a credit line isn\'t rendered', () => {
    const uncredited = { ...DEMO, credit: undefined }
    const lines = renderAnswer(answer({ demo: [uncredited, { ...DEMO, id: 'r_d2', credit: '  ' }] }), en, NOW)

    expect(keys(lines)).not.toContain('ask.answer.demo')
  })

  it('a report whose level or class Lusot can\'t word isn\'t rendered, and the summary still counts it', () => {
    const odd = { ...SHALLOW, level: 'ankle_deep' } as unknown as AskReport
    const lines = renderAnswer(answer({ reports: [DEEP, odd], demo: [], count: 2 }), en, NOW)

    expect(keys(lines)).toEqual(['ask.answer.summaryMany', 'level', 'class', 'ask.answer.where'])
    expect(lines[0].text.text).toBe(`2 reports within 300 m of ${SPOT} in the last 3 hours.`)
  })

  it('the window reads in hours when whole, else in minutes', () => {
    const summary = (windowMin: number) => renderAnswer(answer({ windowMin }), en, NOW)[0].text.text
    expect(summary(60)).toBe(`3 reports within 300 m of ${SPOT} in the last 1 hour.`)
    expect(summary(120)).toBe(`3 reports within 300 m of ${SPOT} in the last 2 hours.`)
    expect(summary(90)).toBe(`3 reports within 300 m of ${SPOT} in the last 90 minutes.`)
    expect(summary(1)).toBe(`3 reports within 300 m of ${SPOT} in the last 1 minute.`)
  })
})

describe('renderAnswer, "dito"', () => {
  const HERE = { name: 'here', source: 'here' } as const

  it('"dito" says "from you", and its no-report line gives the 300 m and the window, in Taglish once reviewed', () => {
    const lines = renderAnswer(answer({ place: HERE }), en, NOW)
    expect(lines[0]).toMatchObject({ key: 'ask.answer.summaryHereMany', text: { text: '3 reports within 300 m of you in the last 3 hours.' } })
    expect(lines.find((line) => line.key === 'ask.answer.whereHere')?.text.text).toBe('Photo taken 25 min ago, 120 m from you.')
    expect(keys(lines)).not.toContain('ask.answer.where')

    const none = answer({ kind: 'no_reports', place: HERE, ...EMPTY })
    expect(renderAnswer(none, en, NOW)[0].text.text).toBe('No recent reports within 300 m of you in the last 3 hours.')
    expect(renderAnswer(none, fil, NOW)[0].text).toEqual({
      text: 'Walang recent report sa loob ng 300 m mula sa iyo sa nakaraang 3 oras.',
      lang: 'fil',
    })
    // Waiting for review, a screen-line key's Taglish shows its English line (C619, C724).
    withEntry(FIL, 'ask.answer.noReportsHere', { ...FIL['ask.answer.noReportsHere'], reviewed: false }, () => {
      expect(renderAnswer(none, fil, NOW)[0].text).toEqual({
        text: 'No recent reports within 300 m of you in the last 3 hours.',
        lang: 'en',
      })
    })
  })
})

describe('renderAnswer, both languages', () => {
  it('an English line on a Taglish screen fills its time and window in English too', () => {
    // Both lines are reviewed now, so make them wait for review here.
    withEntry(FIL, 'ask.answer.summaryMany', { ...FIL['ask.answer.summaryMany'], reviewed: false }, () => {
      withEntry(FIL, 'ask.answer.where', { ...FIL['ask.answer.where'], reviewed: false }, () => {
        const lines = renderAnswer(answer(), fil, NOW)

        expect(lines[0].text).toEqual({ text: `3 reports within 300 m of ${SPOT} in the last 3 hours.`, lang: 'en' })
        expect(lines.find((line) => line.key === 'ask.answer.where')?.text).toEqual({
          text: `Photo taken 25 min ago, 120 m from ${SPOT}.`,
          lang: 'en',
        })
      })
    })
    // Once reviewed, the Taglish line takes the Taglish age and window.
    const where = renderAnswer(answer(), fil, NOW).find((line) => line.key === 'ask.answer.where')?.text
    expect(where?.lang).toBe('fil')
    expect(where?.text).toContain(fil('result.age.minutes', { min: 25 }).text)
  })

  it('every rendered line passes the banned-word test, and every level line has "at this spot" or "sa spot na ito"', () => {
    const answers: AskAnswer[] = [
      answer({ crossing: true, vehicle: 'light' }),
      answer({ vehicle: 'heavy' }),
      answer({ vehicle: 'on_foot' }),
      answer({ source: 'plain_list', fallback: 'deadline', cited: [] }),
      answer({ place: { name: 'here', source: 'here' } }),
      answer({ kind: 'no_reports', ...EMPTY, demo: [DEMO] }),
      answer({ kind: 'place_too_broad', place: null, ...EMPTY, suggestions: ['Taft Ave in front of PGH'] }),
      ...(['no_place', 'lookup_unavailable', 'outside_metro_manila', 'no_location', 'off_topic', 'no_speech'] as const).map(
        (kind) => answer({ kind, place: null, ...EMPTY }),
      ),
    ]
    // The ask.* lines are reviewed now. One pass makes them all wait for review, so the English fallbacks are checked,
    // and the other leaves them reviewed, so the Taglish is checked too.
    const waiting = Object.fromEntries(
      Object.entries(FIL)
        .filter(([key]) => key.startsWith('ask.'))
        .map(([key, entry]) => [key, { ...entry, reviewed: false }]),
    )
    const original = { ...FIL }
    try {
      for (const reviewed of [false, true]) {
        Object.assign(FIL, original)
        if (!reviewed) Object.assign(FIL, waiting)
        for (const t of [en, fil]) {
          for (const a of answers) {
            const lines = renderAnswer(a, t, NOW)
            expect(lines.length).toBeGreaterThan(0)
            for (const line of lines) {
              // A credit is the photographer's own line, not Lusot's wording.
              if (line.key === 'credit') continue
              expect(line.text.text).not.toMatch(BANNED_WORDS)
              expect(line.text.text).not.toMatch(CROSSING)
              expect(line.text.text).not.toMatch(/\{\w+\}/)
              if (line.key === 'level') expect(line.text.text).toMatch(AT_THIS_SPOT)
            }
          }
        }
      }
    } finally {
      Object.assign(FIL, original)
    }
  })
})

describe('maskBannedWords', () => {
  it('masks each banned word letter by letter and keeps the place', () => {
    expect(maskBannedWords('Ligtas ba sa España cor. Maceda?')).toBe('•••••• ba sa España cor. Maceda?')
  })

  it('masks every form of the two words, whole, and leaves other words alone', () => {
    expect(maskBannedWords('Is it safe to cross? Unsafe, SAFETY!')).toBe('Is it •••• to cross? ••••••, ••••••!')
    expect(maskBannedWords('Kaligtasan muna, makaligtas tayo')).toBe('•••••••••• muna, •••••••••• tayo')
    expect(maskBannedWords('Gaano kalalim sa Taft?')).toBe('Gaano kalalim sa Taft?')
    expect(maskBannedWords('LIGTAS')).not.toMatch(BANNED_WORDS)
  })
})
