// Ask Lusot's saved answers as the lines a person reads (Task 18, spec §10 and N9), for MS7's copy check. The test
// harness (backend/api/test/ask-eval/harness.ts) saves each answer as parts, never as words; this gives each record
// back with `rendered: { en, fil }`, the answer through renderAnswer with the English and the Filipino translator the
// app uses, one line of text per answer line, joined by a newline. scripts/check_copy.mjs --answers reads exactly
// those two fields as product copy, and the record's `transcript` for review only (scripts/copy-rules.json).
//
// Rendering needs a clock, for a card's age ("25 min ago"). Each record is rendered at its own `run` time, the moment
// the harness started the run, so the ages are the ones the run's fixture pins had (they sit `minutesAgo` before it).
// A record that can't be rendered stops the whole file with the record's id: none is skipped, and no message holds any
// of its text.
import { makeT } from '../i18n'
import type { AskAnswer } from '../lib/api'
import { renderAnswer } from './render'

export type Rendered = { en: string; fil: string }
export type RenderedRecord = Record<string, unknown> & { rendered: Rendered }

// What renderAnswer reads of an answer, checked before it is called: a missing list or count would give "NaN minutes"
// or a thrown TypeError, not a refusal. (The app's readAnswer in lib/api.ts checks the whole of §5.3 on the way in.)
function isRenderable(a: unknown): a is AskAnswer {
  if (typeof a !== 'object' || a === null || Array.isArray(a)) return false
  const x = a as Record<string, unknown>
  const place = x.place as Record<string, unknown> | null | undefined
  return (
    typeof x.kind === 'string' &&
    typeof x.crossing === 'boolean' &&
    [x.reports, x.demo, x.cited, x.suggestions].every(Array.isArray) &&
    Number.isInteger(x.windowMin) &&
    Number.isInteger(x.count) &&
    (place === null || (typeof place === 'object' && typeof place.name === 'string'))
  )
}

// One record with its rendered lines. Fails with the record's id (and the id alone) when it has no id, no run time,
// no answer renderAnswer can read, or an answer that words nothing.
export function renderRecord(record: Record<string, unknown>): RenderedRecord {
  const id = record.id
  if (typeof id !== 'string' || id === '') throw new Error('an answers record has no id')
  const run = typeof record.run === 'string' ? Date.parse(record.run) : Number.NaN
  if (Number.isNaN(run)) throw new Error(`record ${id}: no run time to render at`)
  if (!isRenderable(record.answer)) throw new Error(`record ${id}: the answer can't be rendered (missing or malformed)`)

  const now = new Date(run)
  const lines = (lang: 'en' | 'fil'): string => {
    try {
      return renderAnswer(record.answer as AskAnswer, makeT(lang), now)
        .map((line) => line.text.text)
        .join('\n')
    } catch (err) {
      throw new Error(`record ${id}: renderAnswer failed (${err instanceof Error ? err.name : 'unknown'})`)
    }
  }
  const rendered: Rendered = { en: lines('en'), fil: lines('fil') }
  if (rendered.en === '' || rendered.fil === '') throw new Error(`record ${id}: the answer words no line`)
  return { ...record, rendered }
}

// A whole answers.jsonl: every record rendered, one JSON line each, in order. Blank lines are allowed (and CRLF), a
// line that isn't a JSON object stops the file with its number, and a file with no record is refused.
export function renderAnswersJsonl(text: string): string {
  const out: string[] = []
  text.split(/\r?\n/).forEach((line, index) => {
    if (line.trim() === '') return
    let record: unknown
    try {
      record = JSON.parse(line)
    } catch {
      throw new Error(`answers file: line ${index + 1} is not JSON`)
    }
    if (typeof record !== 'object' || record === null || Array.isArray(record)) {
      throw new Error(`answers file: line ${index + 1} is not a JSON object`)
    }
    out.push(JSON.stringify(renderRecord(record as Record<string, unknown>)))
  })
  if (out.length === 0) throw new Error('answers file: no records')
  return `${out.join('\n')}\n`
}

// One path part names sealed as Windows reads it: in any case, by its name before any ":" (the NTFS stream
// sealed::$INDEX_ALLOCATION), without trailing dots and spaces. The harness's rule (its isSealedName), word for word.
const isSealedName = (part: string): boolean => part.split(':', 1)[0].replace(/[. ]+$/, '').toLowerCase() === 'sealed'

// Refuses a path with a part named sealed, as given and in any other form the caller passes (such as the absolute
// one). It reads the strings only, never the disk, and its message holds no part of the path.
export function refuseSealed(...forms: string[]): void {
  for (const form of forms) {
    if (form.split(/[\\/]+/).some(isSealedName)) throw new Error('refused: the path is inside a folder named sealed')
  }
}

// answers.rendered.jsonl in the answers file's own folder, with that folder's separator style. Refuses a sealed path.
export function renderedPathFor(answersFile: string): string {
  refuseSealed(answersFile)
  const cut = Math.max(answersFile.lastIndexOf('/'), answersFile.lastIndexOf('\\'))
  return `${answersFile.slice(0, cut + 1)}answers.rendered.jsonl`
}

// The disk, as renderAnswersFile needs it: the run test passes Node's, a test passes fakes. This module imports no Node
// API, since the app's own build has no Node types.
export type FileIo = { resolve(path: string): string; read(path: string): string; write(path: string, text: string): void }

// The file step of `npm run ask:render`: reads the answers file, writes answers.rendered.jsonl beside it, and gives the
// counts back (records, and the English and Filipino lines they hold), never any text. A sealed path is refused, as
// given and as made absolute, before anything is read; nothing is written unless every record rendered.
export function renderAnswersFile(
  file: string,
  io: FileIo,
): { out: string; records: number; linesEn: number; linesFil: number } {
  const absolute = io.resolve(file)
  refuseSealed(file, absolute)
  const out = renderedPathFor(absolute)
  const text = renderAnswersJsonl(io.read(file))
  io.write(out, text)
  const rendered = text
    .trimEnd()
    .split('\n')
    .map((line) => (JSON.parse(line) as RenderedRecord).rendered)
  const count = (lang: 'en' | 'fil') => rendered.reduce((n, r) => n + r[lang].split('\n').length, 0)
  return { out, records: rendered.length, linesEn: count('en'), linesFil: count('fil') }
}
