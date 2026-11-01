// Ask Lusot's saved answers as the lines a person reads (Task 18, spec §10 and N9), for MS7's copy check. The test
// harness (backend/api/test/ask-eval/harness.ts) saves each answer as parts, never as words; this gives each record
// back with `rendered: { en, fil }`, the answer through renderAnswer with the English and the Filipino translator the
// app uses, one line of text per answer line, joined by a newline. scripts/check_copy.mjs --answers reads exactly
// those two fields as product copy, and the record's `transcript` for review only (scripts/copy-rules.json).
//
// Rendering needs a clock, for a card's age ("25 min ago"). The harness places each question's fixture pins when that
// question reads them, so each record is rendered at its own `at`, the question's start. A record from before the
// harness saved `at` falls back to `run`, the start of the whole run, which reads a later question's cards too young.
//
// A question that failed (a status other than 200, so no answer) has nothing to render: it is left out and counted.
// Anything else that can't be rendered, a 200 included, stops the whole file with the record's id, and no message holds
// any of its text.
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
  // The question's own start, else (an older record) the run's.
  const clock = record.at === undefined ? record.run : record.at
  const time = typeof clock === 'string' ? Date.parse(clock) : Number.NaN
  if (Number.isNaN(time)) throw new Error(`record ${id}: no ${record.at === undefined ? 'run' : 'start'} time to render at`)
  if (!isRenderable(record.answer)) throw new Error(`record ${id}: the answer can't be rendered (missing or malformed)`)

  const now = new Date(time)
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

// A question that failed: a status other than 200 and no answer (the harness writes `answer: null` for any non-200).
const questionFailed = (record: Record<string, unknown>): boolean =>
  typeof record.status === 'number' && record.status !== 200 && record.answer === null

// A whole answers.jsonl: every record rendered, one JSON line each, in order, and the number of failed questions left
// out. Blank lines are allowed (and CRLF), a line that isn't a JSON object stops the file with its number, and a file
// with nothing to render is refused.
export function renderAnswersJsonl(text: string): { jsonl: string; rendered: number; skipped: number } {
  const out: string[] = []
  let skipped = 0
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
    if (questionFailed(record as Record<string, unknown>)) {
      skipped++
      return
    }
    out.push(JSON.stringify(renderRecord(record as Record<string, unknown>)))
  })
  if (out.length === 0) {
    throw new Error(skipped === 0 ? 'answers file: no records' : `answers file: no records to render (${skipped} failed questions left out)`)
  }
  return { jsonl: `${out.join('\n')}\n`, rendered: out.length, skipped }
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

// The disk, as renderAnswersFile needs it: the run test passes Node's, a test passes fakes. `repo` is the repo's root.
// This module imports no Node API, since the app's own build has no Node types.
export type FileIo = {
  repo: string
  resolve(path: string): string
  read(path: string): string
  write(path: string, text: string): void
}

// A path as compared for "inside the repo": slashes forward, no trailing slash, and lower case, as the harness's
// answersPath compares them.
const compared = (path: string): string => path.replace(/[\\/]+/g, '/').replace(/\/$/, '').toLowerCase()

// The file step of `npm run ask:render`: reads the answers file, writes answers.rendered.jsonl beside it, and gives the
// counts back (records rendered, failed questions left out, and the English and Filipino lines), never any text. A
// sealed path, or one inside the repo (where git could pick the answers up), is refused, as given and as made
// absolute, before anything is read; nothing is written unless every record that has an answer rendered.
export function renderAnswersFile(
  file: string,
  io: FileIo,
): { out: string; records: number; skipped: number; linesEn: number; linesFil: number } {
  const absolute = io.resolve(file)
  refuseSealed(file, absolute)
  const repo = compared(io.repo)
  for (const form of [file, absolute]) {
    const path = compared(form)
    if (path === repo || path.startsWith(`${repo}/`)) throw new Error('refused: the path is inside the repo')
  }
  const out = renderedPathFor(absolute)
  const done = renderAnswersJsonl(io.read(file))
  io.write(out, done.jsonl)
  const rendered = done.jsonl
    .trimEnd()
    .split('\n')
    .map((line) => (JSON.parse(line) as RenderedRecord).rendered)
  const count = (lang: 'en' | 'fil') => rendered.reduce((n, r) => n + r[lang].split('\n').length, 0)
  return { out, records: done.rendered, skipped: done.skipped, linesEn: count('en'), linesFil: count('fil') }
}
