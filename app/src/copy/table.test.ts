import { expect, it } from 'vitest'
import { EN, type Entry } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { makeT } from '../i18n'
import { LEVELS } from './levels'
import { levelLine } from './wording'
import { copyTable, levelLineTable, screenOf } from './table'

const entry = (text: string, reviewed = false): Entry => ({ text, reviewed })

it('a key names its screen: its first part, or the listed screen after a screen-line prefix when it has three', () => {
  expect(screenOf('nav.map')).toBe('nav')
  expect(screenOf('result.noFlood')).toBe('result')
  expect(screenOf('result.landmark.hub')).toBe('result')
  expect(screenOf('refusal.sample.cantTell')).toBe('sample')
  expect(screenOf('retake.map.tip')).toBe('map')
})

it('a middle part that is no listed screen leaves a screen-line key on the screen that shows it', () => {
  expect(screenOf('retake.check.dark')).toBe('report')
  expect(screenOf('refusal.somewhere.x')).toBe('result')
  expect(screenOf('reason.too_dark.detail')).toBe('result')
})

it('consent and privacy are screens: a key of three or more parts stays on its own, whatever its middle part', () => {
  expect(screenOf('consent.adult.label')).toBe('consent')
  expect(screenOf('privacy.photos.body')).toBe('privacy')
  expect(screenOf('consent.privacy.link')).toBe('consent')
  expect(screenOf('privacy.consent.link')).toBe('privacy')
  expect(screenOf('privacy.retention.days.note')).toBe('privacy')
})

it('a screen-line key with no screen of its own sits on the screen that shows it', () => {
  expect(screenOf('refusal.d19')).toBe('result')
  expect(screenOf('reason.too_dark')).toBe('result')
  expect(screenOf('tip.water_unsure')).toBe('result')
  expect(screenOf('retake.tip')).toBe('report')
  expect(screenOf('consent.title')).toBe('consent')
  expect(screenOf('privacy.title')).toBe('privacy')
})

it('the table has a header, a divider and one row per line, with key, English, Taglish and the marks', () => {
  const table = copyTable({ 'nav.map': entry('Map', true) }, { 'nav.map': entry('Mapa') })
  expect(table.split('\n')).toEqual([
    '| Key | English | Taglish | Reviewed |',
    '| --- | --- | --- | --- |',
    '| `nav.map` | Map | Mapa | en yes, fil no |',
  ])
})

it('the rows run by screen, in the order the app shows them, and the unknown screens come last by name', () => {
  const keys = ['zeta.one', 'privacy.title', 'result.noFlood', 'about.x', 'reason.too_dark', 'nav.map', 'alpha.one', 'layout.noApi']
  const en = Object.fromEntries(keys.map((key) => [key, entry(key)]))
  const rows = copyTable(en, en).split('\n').slice(2)
  const order = rows.map((row) => /`([^`]+)`/.exec(row)?.[1])
  expect(order).toEqual([
    'nav.map',
    'layout.noApi',
    'result.noFlood',
    'reason.too_dark', // the same screen as result.noFlood, in table order
    'about.x',
    'privacy.title',
    'alpha.one',
    'zeta.one',
  ])
})

it('three-part consent and privacy keys sort with their screens, not at the end of the table', () => {
  const keys = ['consent.adult.label', 'privacy.photos.body', 'about.x', 'consent.title', 'privacy.title', 'zeta.one']
  const en = Object.fromEntries(keys.map((key) => [key, entry(key)]))
  const order = copyTable(en, en)
    .split('\n')
    .slice(2)
    .map((row) => /`([^`]+)`/.exec(row)?.[1])
  expect(order).toEqual([
    'about.x',
    'consent.adult.label', // table order within the consent screen
    'consent.title',
    'privacy.photos.body',
    'privacy.title',
    'zeta.one',
  ])
})

it('a pipe or a line break in a line cannot break its row', () => {
  const table = copyTable({ 'nav.map': entry('One | two\nthree') }, { 'nav.map': entry('A|B') })
  const row = table.split('\n')[2]
  expect(row).toBe('| `nav.map` | One \\| two three | A\\|B | en no, fil no |')
  expect(table.split('\n')).toHaveLength(3)
})

it("the real table lists every key of the English table once, with the marks the reviews left", () => {
  const rows = copyTable().split('\n').slice(2)
  expect(rows).toHaveLength(Object.keys(EN).length)
  const marks = (key: string) => rows.find((row) => row.startsWith(`| \`${key}\` |`))
  expect(marks('refusal.d19')).toMatch(/\| en yes, fil yes \|$/)
  expect(marks('layout.screenLine')).toMatch(/\| en yes, fil yes \|$/)
  // Rene's review of Oct 31 passed the lines that changed after M20 (a4d066d), and every other line left.
  expect(marks('report.sendFailed')).toMatch(/\| en yes, fil yes \|$/)
  expect(marks('report.refused.gps_too_coarse')).toMatch(/\| en yes, fil yes \|$/)
  // A line that changes after its review is unreviewed again, in the language that changed.
  const changed = { ...EN, 'report.sendFailed': { ...EN['report.sendFailed'], reviewed: false } }
  const row = copyTable(changed, FIL)
    .split('\n')
    .find((line) => line.startsWith('| `report.sendFailed` |'))
  expect(row).toMatch(/\| en no, fil yes \|$/)
})

it('the level-line table holds each of the 9 levels in its template, then the one floor the rules reach, in both languages', () => {
  const [header, divider, ...rows] = levelLineTable().split('\n')
  expect(header).toBe('| Level | English | Taglish |')
  expect(divider).toBe('| --- | --- | --- |')
  expect(rows).toHaveLength(LEVELS.length + 1)
  const en = makeT('en')
  const fil = makeT('fil')
  LEVELS.forEach((level, place) => {
    expect(rows[place]).toBe(`| \`${level}\` | ${levelLine(en, level, false).text} | ${levelLine(fil, level, false).text} |`)
  })
  expect(rows[LEVELS.length]).toBe(
    `| \`tire\`, at least | ${levelLine(en, 'tire', true).text} | ${levelLine(fil, 'tire', true).text} |`,
  )
})

it('the level-line table reads as people read it: C81\'s English lines, the capital letter in Taglish too', () => {
  const rows = levelLineTable().split('\n').slice(2)
  expect(rows[0]).toMatch(/^\| `below_gutter` \| Below gutter deep at this spot\. \| \p{Lu}/u)
  expect(rows[4]).toMatch(/^\| `knee` \| Knee deep at this spot \(MMDA level\)\. \| \p{Lu}/u)
  expect(rows[8]).toMatch(/^\| `above_chest` \| Above chest deep at this spot\. \| \p{Lu}/u)
  expect(rows[9]).toMatch(/^\| `tire`, at least \| At least tire deep at this spot \(MMDA level\)\. \| /)
  for (const row of rows) expect(row).not.toMatch(/\{\w+\}/)
})

// `npm run copy:table -w app` runs this file and prints the table for Rene's review (C609, M20), then the level
// lines as people read them. Vitest 5's agent reporter hides what a test prints; add `-- --reporter=default`.
it('prints the table', () => {
  console.log(copyTable())
  console.log(`\nLevel lines, as people read them (a level's name set in its template):\n\n${levelLineTable()}`)
})
