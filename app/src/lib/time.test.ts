import { describe, expect, it } from 'vitest'
import { makeT } from '../i18n'
import { ageText, formatDate, formatDateTime, photoDateLine } from './time'

const en = makeT('en')
const fil = makeT('fil')

const NOW = new Date('2026-10-30T10:20:00Z')
const minutesAgo = (minutes: number) => new Date(NOW.getTime() - minutes * 60_000).toISOString()

describe('ageText', () => {
  it('says "just now" for a time in the future, and for under a minute', () => {
    expect(ageText(en, new Date(NOW.getTime() + 90_000).toISOString(), NOW).text).toBe('just now')
    expect(ageText(en, NOW.toISOString(), NOW).text).toBe('just now')
    expect(ageText(en, new Date(NOW.getTime() - 59_000).toISOString(), NOW).text).toBe('just now')
  })

  it('counts minutes up to the hour', () => {
    expect(ageText(en, minutesAgo(1), NOW).text).toBe('1 min ago')
    expect(ageText(en, minutesAgo(25), NOW).text).toBe('25 min ago')
    expect(ageText(en, minutesAgo(59), NOW).text).toBe('59 min ago')
  })

  it('counts hours and minutes after that, and drops "0 min"', () => {
    expect(ageText(en, minutesAgo(60), NOW).text).toBe('1 h ago')
    expect(ageText(en, minutesAgo(125), NOW).text).toBe('2 h 5 min ago')
    expect(ageText(en, minutesAgo(180), NOW).text).toBe('3 h ago')
  })

  it('gives the line in the screen language, marked with it', () => {
    expect(ageText(en, minutesAgo(25), NOW).lang).toBe('en')
    const draft = ageText(fil, minutesAgo(25), NOW)
    expect(draft.lang).toBe('fil')
    expect(draft.text).toContain('25 min')
    expect(draft.text).not.toBe('25 min ago')
  })
})

describe('photoDateLine', () => {
  it('reads "Photo from" with the date, place and event, as the spec words it', () => {
    const line = photoDateLine(en, 'en', { date: '2009-09-26', place: 'Manila', event: 'Typhoon Ondoy' })
    expect(line?.text).toBe('Photo from Sep 26, 2009, Manila, Typhoon Ondoy')
    expect(line?.lang).toBe('en')
  })

  it('keeps a date-only value on its own day, whatever the phone\'s time zone', () => {
    expect(photoDateLine(en, 'en', { date: '2009-09-26' })?.text).toBe('Photo from Sep 26, 2009')
    expect(photoDateLine(en, 'en', { date: '2012-01-01' })?.text).toBe('Photo from Jan 1, 2012')
  })

  it('reads a time in Manila, where the photos are taken', () => {
    // 8:30 PM on Sep 25 in UTC is 4:30 AM on Sep 26 in Manila.
    expect(photoDateLine(en, 'en', { date: '2009-09-25T20:30:00Z' })?.text).toBe('Photo from Sep 26, 2009')
  })

  it('leaves out what it was not given', () => {
    expect(photoDateLine(en, 'en', { place: 'Marikina' })?.text).toBe('Photo from Marikina')
    expect(photoDateLine(en, 'en', { event: 'Typhoon Ondoy' })?.text).toBe('Photo from Typhoon Ondoy')
    expect(photoDateLine(en, 'en', { date: '2009-09-26', event: 'Typhoon Ondoy' })?.text).toBe(
      'Photo from Sep 26, 2009, Typhoon Ondoy',
    )
  })

  it('drops a date it cannot read, and gives no line when nothing is left', () => {
    expect(photoDateLine(en, 'en', { date: 'last week', place: 'Manila' })?.text).toBe('Photo from Manila')
    expect(photoDateLine(en, 'en', { date: 'last week' })).toBeUndefined()
    expect(photoDateLine(en, 'en', {})).toBeUndefined()
    expect(photoDateLine(en, 'en', { place: '  ', event: '' })).toBeUndefined()
  })

  it('words the line in Taglish on a Taglish screen', () => {
    const line = photoDateLine(fil, 'fil', { date: '2009-09-26', place: 'Manila' })
    expect(line?.lang).toBe('fil')
    expect(line?.text).toMatch(/^Photo mula sa .*2009.*Manila$/)
  })
})

describe('the dates the card shows', () => {
  it('formatDate gives a short date, and nothing for a value that is not one', () => {
    expect(formatDate('en', '2026-10-29T14:20:00Z')).toBe('Oct 29, 2026')
    expect(formatDate('en', '2026-10-29')).toBe('Oct 29, 2026')
    expect(formatDate('en', 'soon')).toBeUndefined()
    expect(formatDate('en', '')).toBeUndefined()
  })

  it('formatDateTime gives the time in Manila with its zone', () => {
    expect(formatDateTime('en', '2026-10-30T01:15:00Z')).toMatch(/^Oct 30, 2026, 9:15\sAM GMT\+8$/)
    expect(formatDateTime('en', 'soon')).toBeUndefined()
  })
})
