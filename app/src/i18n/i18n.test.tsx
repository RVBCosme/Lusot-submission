import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { readItem, writeItem } from '../lib/storage'
import { EN, type Entry, type StringKey } from './en'
import { FIL } from './fil'
import { isScreenLineKey, LanguageProvider, Line, makeT, resolveText, T, unreviewedKeys, useLanguage } from './index'

const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
const D19 =
  "I can't tell from this photo. Retake it from a dry spot with a parked car's wheel or a person standing still in view. Don't step into the water or the road."

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('lang')
})

// Puts `entry` in a string table for the length of `run`, then restores the table as it was.
function withEntry(table: Record<string, Entry>, key: string, entry: Entry, run: () => void) {
  const had = Object.hasOwn(table, key)
  const original = table[key]
  table[key] = entry
  try {
    run()
  } finally {
    if (had) table[key] = original
    else delete table[key]
  }
}

// A stand-in for the header's switch, which arrives with the layout (Task 2).
function LanguageButton() {
  const { lang, setLang } = useLanguage()
  const other = lang === 'en' ? 'fil' : 'en'
  return (
    <button type="button" onClick={() => setLang(other)}>
      <T k={other === 'fil' ? 'lang.fil' : 'lang.en'} />
    </button>
  )
}

it('the two locked English lines are the same in Taglish, and reviewed', () => {
  expect(EN['layout.screenLine']).toEqual({
    text: 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.',
    reviewed: true,
  })
  expect(FIL['layout.screenLine']).toEqual(EN['layout.screenLine'])
  expect(FIL['about.notAffiliated'].text).toBe('Not affiliated with MMDA.')
  expect(EN['about.notAffiliated']).toEqual({ text: 'Not affiliated with MMDA.', reviewed: true })
  expect(FIL['about.notAffiliated']).toEqual(EN['about.notAffiliated'])
})

// The banned forms (C608): the two words anywhere in a word, the crossing phrases, and the 9 levels called MMDA's.
const BANNED_WORDS = /safe|ligtas/i
const CROSSING = /you can cross|you can pass|go ahead|pu?wedeng dumaan|tumawid ka|lusutan mo/i
const NINE_LEVELS = /MMDA(['’]?s)? (9|nine) levels|(the )?(9|nine) MMDA levels/i

it('the banned-phrase patterns catch every spelling they stand for', () => {
  for (const s of ['Unsafe', 'SAFETY', 'kaligtasan', 'makaligtas']) expect(s, s).toMatch(BANNED_WORDS)
  const crossing = ['You can cross.', 'you can pass', 'Go ahead', 'Pwedeng dumaan', 'Puwedeng dumaan', 'TUMAWID KA']
  for (const s of [...crossing, 'Lusutan mo']) expect(s, s).toMatch(CROSSING)
  for (const s of ["MMDA's 9 levels", 'MMDA’s nine levels', 'MMDA 9 levels', 'mmda nine levels', 'the 9 MMDA levels']) {
    expect(s, s).toMatch(NINE_LEVELS)
  }
})

it('no string uses a banned word or phrase', () => {
  const all = [...Object.values(EN), ...Object.values(FIL)].map((e) => e.text)
  for (const s of all) {
    expect(s).not.toMatch(BANNED_WORDS)
    expect(s).not.toMatch(CROSSING)
    expect(s).not.toMatch(NINE_LEVELS)
  }
})

it("D19's English refusal and its Taglish are reviewed, and a line that changed after the M20 review isn't", () => {
  expect(EN['refusal.d19']).toEqual({ text: D19, reviewed: true })
  expect(FIL['refusal.d19'].reviewed).toBe(true)
  // M20 (Oct 30) reviewed every key present at a4d066d.
  const nav: StringKey[] = ['nav.map', 'nav.report', 'nav.tested', 'nav.about']
  const layout: StringKey[] = ['lang.en', 'lang.fil', 'lang.switch', 'layout.noApi', 'layout.noApiDetail']
  const titles: StringKey[] = ['privacy.title', 'licences.title', 'pin.title']
  for (const key of [...nav, ...layout, ...titles]) {
    expect(EN[key].reviewed, `en ${key}`).toBe(true)
    expect(FIL[key].reviewed, `fil ${key}`).toBe(true)
  }
  // A line whose text changed after a4d066d is a new line again, until its next review.
  expect(EN['report.sendFailed'].reviewed).toBe(false)
  expect(FIL['report.sendFailed'].reviewed).toBe(false)
  expect(EN['report.refused.gps_too_coarse'].reviewed).toBe(false)
  expect(FIL['report.refused.gps_too_coarse'].reviewed).toBe(true)
})

it('screen-line keys are the refusal, reason, retake, consent and privacy lines', () => {
  for (const key of ['refusal.d19', 'reason.too_dark', 'retake.tip', 'consent.title', 'privacy.title']) {
    expect(isScreenLineKey(key as StringKey), key).toBe(true)
  }
  for (const key of ['nav.map', 'layout.screenLine', 'about.notAffiliated', 'about.privacy.link', 'reasonable.x']) {
    expect(isScreenLineKey(key as StringKey), key).toBe(false)
  }
})

it('resolveText gives English on an English screen, and Taglish on a Taglish one, reviewed or not', () => {
  expect(resolveText('en', 'nav.map')).toEqual({ text: 'Map', lang: 'en' })
  expect(resolveText('en', 'refusal.d19')).toEqual({ text: D19, lang: 'en' })
  expect(FIL['nav.map'].reviewed).toBe(true)
  expect(resolveText('fil', 'nav.map')).toEqual({ text: FIL['nav.map'].text, lang: 'fil' })
  // A draft Taglish line that isn't a screen-line key shows in development builds (C619).
  expect(FIL['report.sendFailed'].reviewed).toBe(false)
  expect(resolveText('fil', 'report.sendFailed')).toEqual({ text: FIL['report.sendFailed'].text, lang: 'fil' })
})

it('resolveText keeps the locked lines, and unreviewed screen-line keys, in English on a Taglish screen', () => {
  expect(resolveText('fil', 'about.notAffiliated')).toEqual({ text: 'Not affiliated with MMDA.', lang: 'en' })
  // The M20 review passed every screen-line key's Taglish, so an unreviewed one is made here.
  const draft = FIL['refusal.d19']
  withEntry(FIL, 'refusal.d19', { ...draft, reviewed: false }, () => {
    expect(resolveText('fil', 'refusal.d19')).toEqual({ text: D19, lang: 'en' })
  })
  // Even a reviewed Taglish line can't replace a locked one.
  withEntry(FIL, 'layout.screenLine', { text: 'Ibang linya', reviewed: true }, () => {
    expect(resolveText('fil', 'layout.screenLine')).toEqual({ text: SCREEN_LINE, lang: 'en' })
  })
})

it('resolveText shows a screen-line key in Taglish once its Taglish is reviewed', () => {
  expect(FIL['refusal.d19'].reviewed).toBe(true)
  expect(resolveText('fil', 'refusal.d19')).toEqual({ text: FIL['refusal.d19'].text, lang: 'fil' })
  const draft = FIL['reason.too_dark']
  withEntry(FIL, 'reason.too_dark', { ...draft, reviewed: false }, () => {
    expect(resolveText('fil', 'reason.too_dark')).toEqual({ text: EN['reason.too_dark'].text, lang: 'en' })
  })
  withEntry(FIL, 'reason.too_dark', { ...draft, reviewed: true }, () => {
    expect(resolveText('fil', 'reason.too_dark')).toEqual({ text: draft.text, lang: 'fil' })
  })
})

it('makeT fills {name} placeholders and leaves the rest as they are', () => {
  const key = 'test.vars' as StringKey
  expect(makeT('en')('nav.map')).toEqual({ text: 'Map', lang: 'en' })
  withEntry(EN, key, { text: 'From {count} of {total}, {missing} {toString}', reviewed: false }, () => {
    withEntry(FIL, key, { text: 'Mula sa {count}', reviewed: false }, () => {
      expect(makeT('en')(key, { count: 2, total: 'three' })).toEqual({
        text: 'From 2 of three, {missing} {toString}',
        lang: 'en',
      })
      expect(makeT('fil')(key, { count: 0 })).toEqual({ text: 'Mula sa 0', lang: 'fil' })
    })
  })
})

it('unreviewedKeys lists every line still waiting for review, with its language', () => {
  const list = unreviewedKeys()

  expect(list).toContainEqual({ lang: 'en', key: 'report.sendFailed' })
  expect(list).toContainEqual({ lang: 'fil', key: 'report.sendFailed' })
  expect(list).toContainEqual({ lang: 'en', key: 'report.refused.gps_too_coarse' })
  expect(list).not.toContainEqual({ lang: 'fil', key: 'report.refused.gps_too_coarse' })
  expect(list).not.toContainEqual({ lang: 'en', key: 'refusal.d19' })
  expect(list).not.toContainEqual({ lang: 'fil', key: 'layout.screenLine' })
  const waiting = [...Object.values(EN), ...Object.values(FIL)].filter((e) => !e.reviewed)
  expect(list).toHaveLength(waiting.length)
  withEntry(FIL, 'refusal.d19', { ...FIL['refusal.d19'], reviewed: false }, () => {
    expect(unreviewedKeys()).toContainEqual({ lang: 'fil', key: 'refusal.d19' })
  })
})

it('an unreviewed Taglish screen-line key shows its English text, marked lang="en"; a reviewed one shows in Taglish', () => {
  writeItem('lusot.lang', 'fil')
  const draft = FIL['refusal.d19']

  withEntry(FIL, 'refusal.d19', { ...draft, reviewed: false }, () => {
    render(
      <LanguageProvider>
        <p>
          <T k="refusal.d19" />
        </p>
      </LanguageProvider>,
    )
    const line = screen.getByText(D19)
    expect(line.tagName).toBe('SPAN')
    expect(line.getAttribute('lang')).toBe('en')
    expect(screen.queryByText(draft.text)).toBeNull()
  })
  cleanup()

  expect(draft.reviewed).toBe(true)
  render(
    <LanguageProvider>
      <p>
        <T k="refusal.d19" />
      </p>
    </LanguageProvider>,
  )
  const reviewed = screen.getByText(draft.text)
  expect(reviewed.tagName).toBe('P')
  expect(reviewed.getAttribute('lang')).toBeNull()
  expect(screen.queryByText(D19)).toBeNull()
})

it("a line in the screen's own language has no mark, and one in the other language has its own", () => {
  writeItem('lusot.lang', 'fil')

  render(
    <LanguageProvider>
      <p>
        <T k="nav.map" />
      </p>
      <p>
        <Line value={{ text: 'English words', lang: 'en' }} />
      </p>
    </LanguageProvider>,
  )

  expect(screen.getByText(FIL['nav.map'].text).tagName).toBe('P')
  const english = screen.getByText('English words')
  expect(english.tagName).toBe('SPAN')
  expect(english.getAttribute('lang')).toBe('en')
})

it('switching to Taglish sets lang="fil" and is remembered', () => {
  const first = render(
    <LanguageProvider>
      <LanguageButton />
      <p>
        <T k="nav.map" />
      </p>
    </LanguageProvider>,
  )
  expect(document.documentElement.lang).toBe('en')
  expect(readItem('lusot.lang')).toBeNull()
  expect(screen.getByText('Map')).toBeTruthy()

  fireEvent.click(screen.getByRole('button', { name: EN['lang.fil'].text }))

  expect(document.documentElement.lang).toBe('fil')
  expect(readItem('lusot.lang')).toBe('fil')
  expect(screen.getByText(FIL['nav.map'].text)).toBeTruthy()

  first.unmount()
  document.documentElement.removeAttribute('lang')
  render(
    <LanguageProvider>
      <p>
        <T k="nav.map" />
      </p>
    </LanguageProvider>,
  )
  expect(document.documentElement.lang).toBe('fil')
  expect(screen.getByText(FIL['nav.map'].text)).toBeTruthy()
})

it('a stored language the app does not know reads as English', () => {
  writeItem('lusot.lang', 'de')

  render(
    <LanguageProvider>
      <p>
        <T k="nav.map" />
      </p>
    </LanguageProvider>,
  )

  expect(document.documentElement.lang).toBe('en')
  expect(screen.getByText('Map')).toBeTruthy()
})

it('a line outside a LanguageProvider fails loudly', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  expect(() => render(<T k="nav.map" />)).toThrow(/LanguageProvider/)
})
