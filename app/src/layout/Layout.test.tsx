import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { EN, type StringKey } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { resolveText, type Lang } from '../i18n/index'
import { NOTICE_VERSION } from '../lib/consent'
import { writeItem } from '../lib/storage'

const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
const API = 'https://api.example.test'
const PIN = '#/pin/r_0123456789abcdef0123456789abcdef'
// The text a line shows in a language, after the review gate (C619).
const shown = (lang: Lang, key: StringKey) => resolveText(lang, key).text

// Each route, with the string key of its screen's heading. The empty hash is the map. The report screen opens on
// its first step, the camera.
const ROUTES: [hash: string, heading: StringKey][] = [
  ['', 'nav.map'],
  ['#/map', 'nav.map'],
  ['#/report', 'camera.title'],
  ['#/tested', 'nav.tested'],
  ['#/about', 'nav.about'],
  ['#/privacy', 'privacy.title'],
  ['#/licences', 'licences.title'],
  [PIN, 'pin.title'],
]
const NAV: StringKey[] = ['nav.map', 'nav.report', 'nav.tested', 'nav.about']

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  history.replaceState(null, '', '/')
  document.documentElement.removeAttribute('lang')
})

// The app at a route, in a language. App mounts its own LanguageProvider, so nothing else wraps it. `consented`
// keeps the accepted notice, so #/report shows its screen rather than the gate (lib/consent.test.tsx tests that).
function renderApp({
  hash = '',
  lang = 'en',
  apiUrl = API,
  consented = false,
}: { hash?: string; lang?: Lang; apiUrl?: string; consented?: boolean } = {}) {
  history.replaceState(null, '', `/${hash}`)
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  if (consented) writeItem('lusot.consent', JSON.stringify({ adult: true, notice: NOTICE_VERSION }))
  return render(<App apiUrl={apiUrl} />)
}

function navLinks(): HTMLElement[] {
  return within(screen.getByRole('navigation')).getAllByRole('link')
}

function expectOneScreenLine() {
  expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
  const line = screen.getByText(SCREEN_LINE)
  expect(line.getAttribute('lang')).toBe('en')
  // It sits in the bar with the nav, outside the screen that scrolls.
  expect(screen.getByRole('main').contains(line)).toBe(false)
  expect(line.closest('footer')?.contains(screen.getByRole('navigation'))).toBe(true)
  return line
}

describe.each(['en', 'fil'] as const)('in %s', (lang) => {
  it.each(ROUTES)('%j shows its screen and the screen line once, in the bar', (hash, heading) => {
    renderApp({ hash, lang, consented: true })

    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(shown(lang, heading))
    expectOneScreenLine()
  })

  it('the nav has 4 links named by the string table, each with an icon', () => {
    renderApp({ lang })

    const links = navLinks()
    expect(links.map((link) => link.textContent)).toEqual(NAV.map((key) => shown(lang, key)))
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['#/map', '#/report', '#/tested', '#/about'])
    for (const [i, key] of NAV.entries()) {
      expect(screen.getByRole('link', { name: shown(lang, key) })).toBe(links[i])
      expect(links[i].querySelector('svg')?.getAttribute('aria-hidden'), key).toBe('true')
    }
  })
})

it('the nav marks the section the route belongs to', () => {
  const current = () => navLinks().filter((link) => link.getAttribute('aria-current') === 'page')
  const cases: [hash: string, section: StringKey][] = [
    ['', 'nav.map'],
    [PIN, 'nav.map'],
    ['#/report', 'nav.report'],
    ['#/tested', 'nav.tested'],
    ['#/about', 'nav.about'],
    ['#/privacy', 'nav.about'],
    ['#/licences', 'nav.about'],
  ]
  for (const [hash, section] of cases) {
    renderApp({ hash })
    expect(current().map((link) => link.textContent), hash).toEqual([EN[section].text])
    cleanup()
  }
})

it('a link in the nav opens its screen', async () => {
  renderApp()
  expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(EN['nav.map'].text)
  const mapMain = screen.getByRole('main')

  fireEvent.click(screen.getByRole('link', { name: EN['nav.tested'].text }))

  expect(await screen.findByRole('heading', { level: 1, name: EN['nav.tested'].text })).toBeTruthy()
  expect(window.location.hash).toBe('#/tested')
  // A fresh <main>, so the new screen starts at its top rather than at the old screen's scroll position.
  expect(screen.getByRole('main')).not.toBe(mapMain)
  expect(screen.getByRole('link', { name: EN['nav.tested'].text }).getAttribute('aria-current')).toBe('page')
  expectOneScreenLine()
})

it('with no API address, the banner shows and Report is disabled', () => {
  renderApp({ apiUrl: '' })

  const banner = screen.getByRole('alert')
  expect(banner.textContent).toContain(EN['layout.noApi'].text)
  expect(banner.textContent).toContain(EN['layout.noApiDetail'].text)
  const report = screen.getByRole('link', { name: EN['nav.report'].text })
  expect(report.getAttribute('aria-disabled')).toBe('true')
  expect(report.hasAttribute('href')).toBe(false)
  expect(report.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
  expect(navLinks()).toHaveLength(4)
  for (const key of ['nav.map', 'nav.tested', 'nav.about'] as const) {
    const link = screen.getByRole('link', { name: EN[key].text })
    expect(link.hasAttribute('href'), key).toBe(true)
    expect(link.hasAttribute('aria-disabled'), key).toBe(false)
  }
})

it('with an API address, there is no banner and Report is a link', () => {
  renderApp()

  expect(screen.queryByRole('alert')).toBeNull()
  const report = screen.getByRole('link', { name: EN['nav.report'].text })
  expect(report.getAttribute('href')).toBe('#/report')
  expect(report.hasAttribute('aria-disabled')).toBe(false)
})

it('the header holds the title and the language switch, each name in its own language', () => {
  renderApp()

  const header = screen.getByRole('banner')
  expect(header.textContent).toContain('Lusot')
  const group = within(header).getByRole('group', { name: EN['lang.switch'].text })
  const english = within(group).getByRole('button', { name: EN['lang.en'].text })
  const taglish = within(group).getByRole('button', { name: FIL['lang.fil'].text })
  expect([english.getAttribute('lang'), english.getAttribute('aria-pressed')]).toEqual(['en', 'true'])
  expect([taglish.getAttribute('lang'), taglish.getAttribute('aria-pressed')]).toEqual(['fil', 'false'])

  fireEvent.click(taglish)

  expect(document.documentElement.lang).toBe('fil')
  expect(within(header).getByRole('group', { name: FIL['lang.switch'].text })).toBe(group)
  expect(english.textContent).toBe(EN['lang.en'].text)
  expect(taglish.textContent).toBe(FIL['lang.fil'].text)
  expect([english.getAttribute('lang'), english.getAttribute('aria-pressed')]).toEqual(['en', 'false'])
  expect([taglish.getAttribute('lang'), taglish.getAttribute('aria-pressed')]).toEqual(['fil', 'true'])
  expect(navLinks().map((link) => link.textContent)).toEqual(NAV.map((key) => FIL[key].text))
  expectOneScreenLine()

  fireEvent.click(english)

  expect(document.documentElement.lang).toBe('en')
  expect(navLinks().map((link) => link.textContent)).toEqual(NAV.map((key) => EN[key].text))
})

it('with localStorage throwing on every access, the app renders in English and still switches language', () => {
  const blocked = vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
    throw new DOMException('The operation is insecure.', 'SecurityError')
  })

  renderApp()

  expect(blocked).toHaveBeenCalled()
  expect(document.documentElement.lang).toBe('en')
  expect(screen.getByRole('link', { name: EN['nav.map'].text })).toBeTruthy()
  expectOneScreenLine()

  fireEvent.click(screen.getByRole('button', { name: FIL['lang.fil'].text }))

  expect(document.documentElement.lang).toBe('fil')
  expect(screen.getByRole('link', { name: FIL['nav.map'].text })).toBeTruthy()
  expectOneScreenLine()

  fireEvent.click(screen.getByRole('button', { name: EN['lang.en'].text }))

  expect(document.documentElement.lang).toBe('en')
  expect(screen.getByRole('link', { name: EN['nav.map'].text })).toBeTruthy()
})
