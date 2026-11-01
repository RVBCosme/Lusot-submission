/// <reference types="node" />
// `npm run ask:render -w app` (Ask Lusot's Task 18, spec §10 and N9): the harness's answers.jsonl with each answer
// worded, for MS7's `node scripts/check_copy.mjs --answers <rendered file>`. Skipped unless LUSOT_ASK_ANSWERS names the
// file, so every other run of the app's tests passes it by. It writes answers.rendered.jsonl beside that file, refuses
// a path with a part named sealed, and prints counts only: never a question, a transcript or a line of an answer.
// In PowerShell, from the repo root (CLAUDE.md's fallback when LUSOT_DATA_DIR is unset):
//   $d = if ($env:LUSOT_DATA_DIR) { $env:LUSOT_DATA_DIR } else { 'C:\Systems\Lusot\lusot-data' }
//   $env:LUSOT_ASK_ANSWERS = "$d\ask\<date>\answers.jsonl"; npm run ask:render -w app
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { renderAnswersFile } from './renderAnswers'

const ANSWERS = process.env.LUSOT_ASK_ANSWERS

describe.skipIf(!ANSWERS)("Ask Lusot's saved answers, worded for the copy check", () => {
  it('writes answers.rendered.jsonl beside the answers file', () => {
    const done = renderAnswersFile(ANSWERS ?? '', {
      resolve,
      read: (path) => readFileSync(path, 'utf8'),
      write: (path, text) => writeFileSync(path, text, 'utf8'),
    })

    console.log(`ask:render: ${done.records} records, ${done.linesEn} English lines, ${done.linesFil} Filipino lines`)
    console.log('ask:render: written beside the answers file as answers.rendered.jsonl')
    expect(done.records).toBeGreaterThan(0)
  })
})
