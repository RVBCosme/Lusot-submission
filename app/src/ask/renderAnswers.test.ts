import { describe, expect, it, type Mock, vi } from 'vitest'
import copyRules from '../../../scripts/copy-rules.json?raw'
import { makeT } from '../i18n'
import type { AskAnswer, AskReport } from '../lib/api'
import { renderAnswer } from './render'
import { type FileIo, refuseSealed, renderAnswersFile, renderAnswersJsonl, renderedPathFor, renderRecord } from './renderAnswers'

// Made-up fixtures only: nothing here is a real question, answer or place.
const RUN = '2026-11-02T02:00:00.000Z'
const SPOT = 'Made-up Avenue cor. Test St'

const report = (over: Partial<AskReport> = {}): AskReport => ({
  id: 'r_00000000000000000000000000000001',
  lat: 14.6,
  lng: 121,
  capturedAt: '2026-11-02T01:35:00Z', // 25 min before RUN
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
})

const answer = (over: Partial<AskAnswer> = {}): AskAnswer => ({
  source: 'model',
  fallback: null,
  kind: 'reports',
  crossing: false,
  vehicle: null,
  place: { name: SPOT, source: 'spots' },
  windowMin: 180,
  radiusM: 300,
  count: 1,
  reports: [report()],
  demo: [],
  deepestId: 'r_00000000000000000000000000000001',
  cited: ['r_00000000000000000000000000000001'],
  suggestions: [],
  ...over,
})

// A record as the harness writes it (backend/api/test/ask-eval/harness.ts): the answer as parts, and the run's time.
const record = (id: string, a: unknown = answer(), over: Record<string, unknown> = {}) => ({
  run: RUN,
  id,
  route: 'ask',
  ms: 1234,
  status: 200,
  answer: a,
  checks: { status: true },
  pass: true,
  ...over,
})

const joined = (a: AskAnswer, lang: 'en' | 'fil', now = new Date(RUN)) =>
  renderAnswer(a, makeT(lang), now)
    .map((line) => line.text.text)
    .join('\n')

describe('renderRecord', () => {
  it('gives the same record plus rendered.en and rendered.fil, each the answer through renderAnswer joined by a newline', () => {
    const input = record('Q1')

    const out = renderRecord(input)

    expect(out).toEqual({ ...input, rendered: { en: joined(answer(), 'en'), fil: joined(answer(), 'fil') } })
    // The original fields keep their order, with rendered last.
    expect(Object.keys(out)).toEqual([...Object.keys(input), 'rendered'])
    expect(out.rendered.en.split('\n').length).toBeGreaterThan(1)
    expect(out.rendered.en).toContain('Knee deep at this spot')
    expect(out.rendered.fil).not.toBe(out.rendered.en)
  })

  it("renders an older record, which has no `at`, at its run time, so a card's age is the run's and not the clock's", () => {
    const later = record('Q1', answer(), { run: '2026-11-02T04:00:00.000Z' }) // 145 min after the photo

    expect(renderRecord(record('Q1')).rendered.en).toContain('Photo taken 25 min ago,')
    expect(renderRecord(later).rendered.en).toContain('Photo taken 2 h 25 min ago,')
  })

  it("renders at the question's own start time `at`, not the run's, because its fixture pins were placed then", () => {
    // The run began at RUN (02:00); this question started 40 min later, and its pin was placed 25 min before that.
    const fixturePin = report({ capturedAt: '2026-11-02T02:15:00Z' })
    const input = record('Q4', answer({ reports: [fixturePin], deepestId: fixturePin.id }), { at: '2026-11-02T02:40:00.000Z' })

    expect(renderRecord(input).rendered.en).toContain('Photo taken 25 min ago,')
    // Read at the run's start instead, the pin would be 15 min in the future: its card would read "just now".
    expect(renderRecord({ ...input, at: undefined }).rendered.en).toContain('Photo taken just now,')
    expect(Object.keys(renderRecord(input))).toContain('at') // kept, like every field
  })

  it('keeps a spoken record\'s transcript as it is, for the review only', () => {
    const out = renderRecord(record('V1', answer(), { route: 'ask_voice', transcript: 'a made-up transcript' }))

    expect(out).toMatchObject({ route: 'ask_voice', transcript: 'a made-up transcript' })
    expect(out.rendered.en).not.toContain('made-up transcript')
  })

  it.each([
    ['no answer (a failed question)', record('Q7', null), /Q7/],
    ['an answer that is not an object', record('Q8', 'oops'), /Q8/],
    ['an answer with no report lists', record('Q9', { kind: 'reports' }), /Q9/],
    ['an answer of an unknown kind, which words nothing', record('Q10', answer({ kind: 'mystery' as AskAnswer['kind'] })), /Q10/],
    ['no run time', record('Q11', answer(), { run: undefined }), /Q11/],
    ['a run time that is no date', record('Q12', answer(), { run: 'yesterday' }), /Q12/],
    ['an `at` that is no date, though the run time is good', record('Q14', answer(), { at: 'yesterday' }), /Q14/],
    ['an `at` that is not text', record('Q15', answer(), { at: 5 }), /Q15/],
    ['no id', { ...record('x'), id: undefined }, /id/],
  ])('fails loudly, naming the record, for %s', (_name, input, named) => {
    expect(() => renderRecord(input as Record<string, unknown>)).toThrow(named)
  })

  it("never puts the record's answer text in the error", () => {
    const secret = answer({ place: { name: 'A Secret Place Name', source: 'spots' }, reports: 'x' as unknown as AskReport[] })

    expect(() => renderRecord(record('Q13', secret))).toThrow(/Q13/)
    expect(() => renderRecord(record('Q13', secret))).not.toThrow(/Secret/)
  })
})

describe('renderAnswersJsonl', () => {
  it('renders every record, one line each, in order, ending with a newline', () => {
    const lines = [record('Q1'), record('Q2', answer({ kind: 'off_topic', count: 0, reports: [], deepestId: null, cited: [], place: null }))]

    const out = renderAnswersJsonl(`${lines.map((l) => JSON.stringify(l)).join('\n')}\n`)

    const parsed = out.jsonl.trimEnd().split('\n').map((l) => JSON.parse(l))
    expect(out.jsonl.endsWith('\n')).toBe(true)
    expect(parsed.map((p) => p.id)).toEqual(['Q1', 'Q2'])
    expect(parsed[1].rendered.en.length).toBeGreaterThan(0)
    expect(out).toMatchObject({ rendered: 2, skipped: 0 })
  })

  it('accepts blank lines and CRLF, and fails on a line that is not JSON, naming its number', () => {
    const ok = JSON.stringify(record('Q1'))

    expect(JSON.parse(renderAnswersJsonl(`${ok}\r\n\r\n${ok}\r\n`).jsonl.split('\n')[1]).id).toBe('Q1')
    expect(() => renderAnswersJsonl(`${ok}\n{not json\n`)).toThrow(/line 2/)
  })

  it('fails on a file with no record, so an empty file never passes as rendered', () => {
    expect(() => renderAnswersJsonl('')).toThrow(/no records/)
    expect(() => renderAnswersJsonl('\n\n')).toThrow(/no records/)
  })

  it('names a 200 whose answer cannot be rendered, and renders nothing for the file', () => {
    const text = `${JSON.stringify(record('Q1'))}\n${JSON.stringify(record('Q2', null))}\n`

    expect(() => renderAnswersJsonl(text)).toThrow(/Q2/) // status 200, answer null
    expect(() => renderAnswersJsonl(`${JSON.stringify(record('Q3', { kind: 'reports' }))}\n`)).toThrow(/Q3/)
    expect(() => renderAnswersJsonl(`${JSON.stringify(record('Q4', null, { status: undefined }))}\n`)).toThrow(/Q4/)
  })

  it('leaves out a record whose question failed (a status that is not 200, and no answer), and counts it', () => {
    const failed = (id: string, status: number) => JSON.stringify(record(id, null, { status, pass: false }))
    const text = [JSON.stringify(record('Q1')), failed('Q2', 503), failed('Q3', 500), JSON.stringify(record('Q5'))].join('\n')

    const out = renderAnswersJsonl(`${text}\n`)

    expect(out).toMatchObject({ rendered: 2, skipped: 2 })
    expect(out.jsonl.trimEnd().split('\n').map((l) => JSON.parse(l).id)).toEqual(['Q1', 'Q5'])
  })

  it('still renders a record with a status that is not 200 but an answer, and refuses a file where every record failed', () => {
    const odd = JSON.stringify(record('Q1', answer(), { status: 206 }))
    expect(renderAnswersJsonl(`${odd}\n`)).toMatchObject({ rendered: 1, skipped: 0 })

    const allFailed = `${JSON.stringify(record('Q2', null, { status: 503 }))}\n${JSON.stringify(record('Q3', null, { status: 500 }))}\n`
    expect(() => renderAnswersJsonl(allFailed)).toThrow(/no records.*2 .*failed/)
  })
})

describe('the output path and the sealed rule', () => {
  it('writes answers.rendered.jsonl beside the answers file, in the same folder and separator style', () => {
    expect(renderedPathFor('C:\\data\\ask\\2026-11-02\\answers.jsonl')).toBe('C:\\data\\ask\\2026-11-02\\answers.rendered.jsonl')
    expect(renderedPathFor('/data/ask/2026-11-02/answers.jsonl')).toBe('/data/ask/2026-11-02/answers.rendered.jsonl')
    expect(renderedPathFor('answers.jsonl')).toBe('answers.rendered.jsonl')
  })

  it('refuses a path with a part named sealed, in every spelling the harness refuses', () => {
    for (const sealed of ['sealed', 'Sealed', 'SEALED.', 'sealed ', 'sealed::$INDEX_ALLOCATION']) {
      expect(() => refuseSealed(`C:\\data\\${sealed}\\ask\\answers.jsonl`), sealed).toThrow(/sealed/)
      expect(() => refuseSealed(`/data/${sealed}/answers.jsonl`), sealed).toThrow(/sealed/)
      expect(() => renderedPathFor(`C:\\data\\${sealed}\\answers.jsonl`), sealed).toThrow(/sealed/)
    }
    expect(() => refuseSealed('C:\\data\\unsealed\\answers.jsonl')).not.toThrow()
    expect(() => refuseSealed('C:\\data\\ask\\2026-11-02\\answers.jsonl')).not.toThrow()
  })

  it('also refuses a second form of the path, such as the absolute one', () => {
    expect(() => refuseSealed('answers.jsonl', 'D:\\x\\sealed\\answers.jsonl')).toThrow(/sealed/)
  })
})

describe('renderAnswersFile', () => {
  const FILE = 'C:\\data\\ask\\2026-11-02\\answers.jsonl'
  const lines = `${[record('Q1'), record('Q2', answer({ kind: 'no_reports', count: 0, reports: [], deepestId: null, cited: [] }))]
    .map((r) => JSON.stringify(r))
    .join('\n')}\n`
  type FakeIo = { repo: string; resolve: FileIo['resolve']; read: Mock<FileIo['read']>; write: Mock<FileIo['write']> }
  const io = (over: Partial<FakeIo> = {}): FakeIo => ({
    repo: 'C:\\repo\\lusot',
    resolve: (p) => p,
    read: vi.fn<FileIo['read']>(() => lines),
    write: vi.fn<FileIo['write']>(),
    ...over,
  })

  it('reads the answers file and writes answers.rendered.jsonl beside it, giving only counts back', () => {
    const fake = io()

    const done = renderAnswersFile(FILE, fake)

    expect(fake.read).toHaveBeenCalledWith(FILE)
    expect(fake.write).toHaveBeenCalledTimes(1)
    const [path, text] = fake.write.mock.calls[0] as [string, string]
    expect(path).toBe('C:\\data\\ask\\2026-11-02\\answers.rendered.jsonl')
    expect(text).toBe(renderAnswersJsonl(lines).jsonl)
    expect(done.records).toBe(2)
    expect(done.skipped).toBe(0)
    expect(done.out).toBe(path)
    // Counts, never text: the numbers of records, failed questions left out and lines, and the path.
    expect(Object.keys(done).sort()).toEqual(['linesEn', 'linesFil', 'out', 'records', 'skipped'])
    expect(done.linesEn).toBeGreaterThan(done.records)
  })

  it('counts the failed questions it leaves out, and writes only the rest', () => {
    const failedLine = JSON.stringify(record('Q9', null, { status: 503 }))
    const fake = io({ read: vi.fn(() => `${lines}${failedLine}\n`) })

    const done = renderAnswersFile(FILE, fake)

    expect(done).toMatchObject({ records: 2, skipped: 1 })
    expect((fake.write.mock.calls[0] as [string, string])[1]).toBe(renderAnswersJsonl(lines).jsonl)
  })

  it('refuses a path inside the repo before it reads anything, as answersPath does, as given or made absolute', () => {
    const inside = io()
    expect(() => renderAnswersFile('C:\\repo\\lusot\\out\\answers.jsonl', inside)).toThrow(/inside the repo/)
    expect(() => renderAnswersFile('c:/REPO/lusot/answers.jsonl', inside)).toThrow(/inside the repo/) // case and slashes
    expect(() => renderAnswersFile('C:\\repo\\lusot', inside)).toThrow(/inside the repo/)
    const relative = io({ resolve: () => 'C:\\repo\\lusot\\data\\answers.jsonl' })
    expect(() => renderAnswersFile('data\\answers.jsonl', relative)).toThrow(/inside the repo/)
    for (const f of [inside, relative]) {
      expect(f.read).not.toHaveBeenCalled()
      expect(f.write).not.toHaveBeenCalled()
    }
    // A sibling folder that only starts with the repo's name is outside it.
    expect(() => renderAnswersFile('C:\\repo\\lusot-data\\ask\\answers.jsonl', io())).not.toThrow()
  })

  it('refuses a sealed path before it reads anything, as given or as made absolute', () => {
    const fake = io()
    expect(() => renderAnswersFile('C:\\data\\sealed\\answers.jsonl', fake)).toThrow(/sealed/)
    const absolute = io({ resolve: () => 'D:\\x\\Sealed.\\answers.jsonl' })
    expect(() => renderAnswersFile('answers.jsonl', absolute)).toThrow(/sealed/)
    for (const f of [fake, absolute]) {
      expect(f.read).not.toHaveBeenCalled()
      expect(f.write).not.toHaveBeenCalled()
    }
  })

  it('writes nothing when a record cannot be rendered', () => {
    const fake = io({ read: vi.fn(() => `${JSON.stringify(record('Q1'))}\n${JSON.stringify(record('Q2', null))}\n`) })

    expect(() => renderAnswersFile(FILE, fake)).toThrow(/Q2/)
    expect(fake.write).not.toHaveBeenCalled()
  })
})

describe("the fields match MS7's copy check", () => {
  // scripts/copy-rules.json's `answers` names the fields scripts/check_copy.mjs reads (product copy, and the
  // transcript for review only). The renderer's output has exactly those, at those paths.
  const rules = (JSON.parse(copyRules) as { answers: { fields: string[]; reviewFields: string[] } }).answers
  const pick = (obj: unknown, path: string) =>
    path.split('.').reduce<unknown>((o, k) => (o !== null && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), obj)

  it('every product-copy field is a string in the rendered record, and the review field is the record\'s transcript', () => {
    const out = renderRecord(record('V1', answer(), { route: 'ask_voice', transcript: 'a made-up transcript' }))

    expect(rules.fields).toEqual(['rendered.en', 'rendered.fil'])
    for (const field of rules.fields) expect(typeof pick(out, field), field).toBe('string')
    expect(rules.reviewFields).toEqual(['transcript'])
    expect(pick(out, 'transcript')).toBe('a made-up transcript')
  })
})
