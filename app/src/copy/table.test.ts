import { expect, it } from 'vitest'
import { EN, type Entry } from '../i18n/en'
import { copyTable, screenOf } from './table'

const entry = (text: string, reviewed = false): Entry => ({ text, reviewed })

it('a key names its screen: its first part, or the part after a screen-line prefix when it has three', () => {
  expect(screenOf('nav.map')).toBe('nav')
  expect(screenOf('result.noFlood')).toBe('result')
  expect(screenOf('result.landmark.hub')).toBe('result')
  expect(screenOf('refusal.sample.cantTell')).toBe('sample')
  expect(screenOf('retake.check.dark')).toBe('check')
})

it('a screen-line key with no screen of its own sits on the screen that shows it', () => {
  expect(screenOf('refusal.d19')).toBe('result')
  expect(screenOf('reason.too_dark')).toBe('result')
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

it('a pipe or a line break in a line cannot break its row', () => {
  const table = copyTable({ 'nav.map': entry('One | two\nthree') }, { 'nav.map': entry('A|B') })
  const row = table.split('\n')[2]
  expect(row).toBe('| `nav.map` | One \\| two three | A\\|B | en no, fil no |')
  expect(table.split('\n')).toHaveLength(3)
})

it("the real table lists every key of the English table once, and the marks of the lines Rene already fixed", () => {
  const rows = copyTable().split('\n').slice(2)
  expect(rows).toHaveLength(Object.keys(EN).length)
  const d19 = rows.find((row) => row.startsWith('| `refusal.d19` |'))
  expect(d19).toMatch(/\| en yes, fil no \|$/)
  const screenLine = rows.find((row) => row.startsWith('| `layout.screenLine` |'))
  expect(screenLine).toMatch(/\| en yes, fil yes \|$/)
})

// `npm run copy:table -w app` runs this file and prints the table for Rene's review (C609, M20). Vitest 5's agent
// reporter hides what a test prints; add `-- --reporter=default` to read it.
it('prints the table', () => {
  console.log(copyTable())
})
