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
  ['#/ask', 'nav.ask'],
]
const NAV: StringKey[] = ['nav.map', 'nav.report', 'nav.tested', 'nav.about', 'nav.ask']

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

  // Task 18's axe pass found the privacy page's scrolling <main> with nothing a keyboard could focus to scroll it.
  it('the screen that scrolls is a tab stop, so a keyboard can scroll a screen with nothing else to focus', () => {
    renderApp({ hash: '#/privacy', lang })

    expect(screen.getByRole('main').tabIndex).toBe(0)
  })

  it('the nav has 5 links named by the string table, each with an icon', () => {
    renderApp({ lang })

    const links = navLinks()
    expect(links.map((link) => link.textContent)).toEqual(NAV.map((key) => shown(lang, key)))
    expect(links.map((link) => link.getAttribute('href'))).toEqual(['#/map', '#/report', '#/tested', '#/about', '#/ask'])
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
    ['#/ask', 'nav.ask'],
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
  expect(navLinks()).toHaveLength(5)
  for (const key of ['nav.map', 'nav.tested', 'nav.about', 'nav.ask'] as const) {
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

// ---- the desktop layout (from lg, 64 rem) ----
//
// jsdom applies no stylesheet, so these pin the structure the stylesheet works on: which element is a grid, which
// elements hand their children to it, and where each child is placed. The browser's side of it (the nav drawn in the top
// bar, the map across the window, the screen line at the bottom, once) is e2e/desktop.spec.ts's, at 1280 x 800.
describe('the shell from lg', () => {
  const has = (element: Element, ...tokens: string[]) => tokens.every((token) => element.classList.contains(token))
  const banner = () => screen.getByRole('banner')
  const shell = () => banner().parentElement as HTMLElement
  const footer = () => document.querySelector('footer') as HTMLElement
  const after = (first: Node, second: Node) => Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)
  const CENTRED = 'lg:page-x'

  it('has one navigation, after the screen in the page, so the focus order is the phone\'s at every width', () => {
    renderApp()

    expect(screen.getAllByRole('navigation')).toHaveLength(1)
    expect(after(banner(), screen.getByRole('main'))).toBe(true)
    expect(after(screen.getByRole('main'), screen.getByRole('navigation'))).toBe(true)
    expect(footer().contains(screen.getByRole('navigation'))).toBe(true)
  })

  it('is the phone\'s below lg: a column that fills the viewport, the screen scrolling, the bar pinned under it', () => {
    renderApp()

    expect(has(shell(), 'safe-area', 'flex', 'h-screen', 'flex-col')).toBe(true)
    expect(has(screen.getByRole('main'), '-mx-2', 'px-2', 'py-4', 'min-h-0', 'flex-1', 'overflow-y-auto')).toBe(true)
    expect(has(footer(), 'relative', 'z-[1100]', 'shrink-0', 'bg-surface')).toBe(true)
    expect(has(banner(), 'flex', 'flex-wrap', 'justify-between', 'border-b')).toBe(true)
    // The bottom bar's links are still an icon over a label, in a row that shares the width.
    const link = screen.getByRole('link', { name: EN['nav.map'].text })
    expect(has(link, 'flex', 'flex-col', 'min-h-tap')).toBe(true)
    expect(has(link.parentElement as HTMLElement, 'flex-1')).toBe(true)
  })

  it('is a grid at lg: the top bar, the notices, the screen and the screen line, in four rows', () => {
    renderApp({ apiUrl: '' })

    expect(has(shell(), 'lg:grid', 'lg:grid-cols-[auto_minmax(0,1fr)_auto]', 'lg:grid-rows-[auto_auto_minmax(0,1fr)_auto]')).toBe(true)
    // The header and the footer give their children to the grid. The nav stays in the footer in the page, and is drawn in
    // the bar: the brand, then the nav, then the language switch, side by side in the first row.
    expect(has(banner(), 'lg:contents')).toBe(true)
    expect(has(footer(), 'lg:contents')).toBe(true)
    expect(has(within(banner()).getByText('Lusot'), 'lg:col-start-1', 'lg:row-start-1')).toBe(true)
    expect(has(screen.getByRole('navigation'), 'lg:col-start-2', 'lg:row-start-1')).toBe(true)
    expect(has(within(banner()).getByRole('group'), 'lg:col-start-3', 'lg:row-start-1')).toBe(true)
    // The notices share the second row, one above the other, across the width.
    expect(has(screen.getByRole('alert').parentElement as HTMLElement, 'lg:col-span-full', 'lg:row-start-2')).toBe(true)
    expect(has(screen.getByRole('main'), 'lg:col-span-full', 'lg:row-start-3')).toBe(true)
    expect(has(screen.getByText(SCREEN_LINE), 'lg:col-span-full', 'lg:row-start-4')).toBe(true)
  })

  it('has a row for the notices whether or not any shows, and the offline banner is in it', () => {
    renderApp()

    const notices = screen.getByRole('main').previousElementSibling as HTMLElement
    expect(has(notices, 'lg:row-start-2')).toBe(true)
    expect(notices.textContent).toBe('')
  })

  it('centres every screen at 72 rem, except the map, which runs to the edges of the window', () => {
    for (const hash of ['#/about', '#/tested', '#/ask', '#/privacy', PIN]) {
      renderApp({ hash })
      const main = screen.getByRole('main')
      expect(has(main, 'lg:mx-0', CENTRED), hash).toBe(true)
      expect(main.classList.contains('lg:p-0'), hash).toBe(false)
      cleanup()
    }
    for (const hash of ['', '#/map']) {
      renderApp({ hash })
      const main = screen.getByRole('main')
      expect(has(main, 'lg:mx-0', 'lg:p-0'), hash).toBe(true)
      expect(main.classList.contains(CENTRED), hash).toBe(false)
      cleanup()
    }
  })

  it('draws the nav as a row of icon and label from lg, each link with the same current-page underline', () => {
    renderApp()

    const link = screen.getByRole('link', { name: EN['nav.map'].text })
    expect(has(link, 'lg:flex-row', 'lg:gap-2', 'lg:px-3')).toBe(true)
    expect(has(link.parentElement as HTMLElement, 'lg:flex-none')).toBe(true)
    expect(link.className).toContain('aria-[current=page]:underline')
    expect(link.getAttribute('aria-current')).toBe('page')
  })
})
