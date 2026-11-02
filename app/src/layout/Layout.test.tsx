import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import masterMark from '../../brand/lusot-mark.svg?raw'
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

// The page holds two copies of the nav (see 'the shell from lg'): one in the header, drawn from lg, and one in the footer,
// drawn below it. jsdom applies no stylesheet, so it sees both; these helpers pick one, and the tests of the structure
// say what each one is.
const phoneNav = () => within(document.querySelector('footer') as HTMLElement).getByRole('navigation')
const desktopNav = () => within(screen.getByRole('banner')).getByRole('navigation')

function navLinks(): HTMLElement[] {
  return within(phoneNav()).getAllByRole('link')
}

function expectOneScreenLine() {
  expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
  const line = screen.getByText(SCREEN_LINE)
  expect(line.getAttribute('lang')).toBe('en')
  // It sits in the bar with the nav, outside the screen that scrolls.
  expect(screen.getByRole('main').contains(line)).toBe(false)
  expect(line.closest('footer')?.contains(phoneNav())).toBe(true)
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
      expect(within(phoneNav()).getByRole('link', { name: shown(lang, key) })).toBe(links[i])
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

  fireEvent.click(within(phoneNav()).getByRole('link', { name: EN['nav.tested'].text }))

  expect(await screen.findByRole('heading', { level: 1, name: EN['nav.tested'].text })).toBeTruthy()
  expect(window.location.hash).toBe('#/tested')
  // A fresh <main>, so the new screen starts at its top rather than at the old screen's scroll position.
  expect(screen.getByRole('main')).not.toBe(mapMain)
  expect(within(phoneNav()).getByRole('link', { name: EN['nav.tested'].text }).getAttribute('aria-current')).toBe('page')
  expectOneScreenLine()
})

it('with no API address, the banner shows and Report is disabled', () => {
  renderApp({ apiUrl: '' })

  const banner = screen.getByRole('alert')
  expect(banner.textContent).toContain(EN['layout.noApi'].text)
  expect(banner.textContent).toContain(EN['layout.noApiDetail'].text)
  const report = within(phoneNav()).getByRole('link', { name: EN['nav.report'].text })
  expect(report.getAttribute('aria-disabled')).toBe('true')
  expect(report.hasAttribute('href')).toBe(false)
  expect(report.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
  expect(navLinks()).toHaveLength(5)
  for (const key of ['nav.map', 'nav.tested', 'nav.about', 'nav.ask'] as const) {
    const link = within(phoneNav()).getByRole('link', { name: EN[key].text })
    expect(link.hasAttribute('href'), key).toBe(true)
    expect(link.hasAttribute('aria-disabled'), key).toBe(false)
  }
})

it('with an API address, there is no banner and Report is a link', () => {
  renderApp()

  expect(screen.queryByRole('alert')).toBeNull()
  const report = within(phoneNav()).getByRole('link', { name: EN['nav.report'].text })
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
  expect(within(phoneNav()).getByRole('link', { name: EN['nav.map'].text })).toBeTruthy()
  expectOneScreenLine()

  fireEvent.click(screen.getByRole('button', { name: FIL['lang.fil'].text }))

  expect(document.documentElement.lang).toBe('fil')
  expect(within(phoneNav()).getByRole('link', { name: FIL['nav.map'].text })).toBeTruthy()
  expectOneScreenLine()

  fireEvent.click(screen.getByRole('button', { name: EN['lang.en'].text }))

  expect(document.documentElement.lang).toBe('en')
  expect(within(phoneNav()).getByRole('link', { name: EN['nav.map'].text })).toBeTruthy()
})

// ---- the desktop layout (from lg, 64 rem) ----
//
// jsdom applies no stylesheet, so these pin the structure the stylesheet works on: which element is a grid, which
// elements hand their children to it, where each child is placed, and which copy of the nav each width shows. The
// browser's side of it (the nav drawn in the top bar, the map across the window, the screen line at the bottom, once, and
// the Tab order) is e2e/desktop.spec.ts's, at 1280 x 800.
describe('the shell from lg', () => {
  const has = (element: Element, ...tokens: string[]) => tokens.every((token) => element.classList.contains(token))
  const banner = () => screen.getByRole('banner')
  const shell = () => banner().parentElement as HTMLElement
  const footer = () => document.querySelector('footer') as HTMLElement
  const after = (first: Node, second: Node) => Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)
  const CENTRED = 'lg:page-x'

  // One copy for each width, the other not displayed (display: none is out of the tab order and the accessibility tree), so
  // a screen reader finds one navigation landmark at any width, and the keyboard follows what the eye sees: at lg the
  // brand, the nav, the language switch, then the screen; below lg the screen, then the bar of tabs (WCAG 2.4.3, 1.3.2).
  it('draws the nav twice, one in the header from lg and one in the footer below it, each hidden at the other width', () => {
    renderApp()

    expect(screen.getAllByRole('navigation')).toEqual([desktopNav(), phoneNav()])
    expect(has(desktopNav(), 'hidden', 'lg:block')).toBe(true)
    expect(desktopNav().classList.contains('lg:hidden')).toBe(false)
    expect(has(phoneNav(), 'lg:hidden')).toBe(true)
    expect(phoneNav().classList.contains('hidden')).toBe(false)
    expect(banner().contains(desktopNav())).toBe(true)
    expect(footer().contains(phoneNav())).toBe(true)
  })

  it('puts the header\'s nav between the brand and the language switch and the footer\'s after the screen, in the page', () => {
    renderApp()

    const brand = within(banner()).getByText('Lusot')
    const switcher = within(banner()).getByRole('group')
    expect(after(brand, desktopNav())).toBe(true)
    expect(after(desktopNav(), switcher)).toBe(true)
    expect(after(switcher, screen.getByRole('main'))).toBe(true)
    expect(after(screen.getByRole('main'), phoneNav())).toBe(true)
  })

  it('gives both copies the same five links, with the same current section marked and Report disabled alike', () => {
    const links = (nav: HTMLElement) =>
      within(nav)
        .getAllByRole('link')
        .map((link) => [
          link.textContent,
          link.getAttribute('href'),
          link.getAttribute('aria-current'),
          link.getAttribute('aria-disabled'),
        ])

    renderApp({ hash: '#/tested' })
    expect(links(desktopNav())).toHaveLength(5)
    expect(links(desktopNav())).toEqual(links(phoneNav()))
    expect(links(desktopNav()).filter(([, , current]) => current === 'page')).toEqual([
      [EN['nav.tested'].text, '#/tested', 'page', null],
    ])
    cleanup()

    renderApp({ apiUrl: '' })
    expect(links(desktopNav())).toEqual(links(phoneNav()))
    expect(links(desktopNav()).filter(([, , , disabled]) => disabled === 'true')).toEqual([[EN['nav.report'].text, null, null, 'true']])
  })

  it('is the phone\'s below lg: a column that fills the viewport, the screen scrolling, the bar pinned under it', () => {
    renderApp()

    expect(has(shell(), 'safe-area', 'flex', 'h-screen', 'flex-col')).toBe(true)
    expect(has(screen.getByRole('main'), '-mx-2', 'px-2', 'py-4', 'min-h-0', 'flex-1', 'overflow-y-auto')).toBe(true)
    expect(has(footer(), 'relative', 'z-[1100]', 'shrink-0', 'bg-surface')).toBe(true)
    expect(has(banner(), 'app-bar', 'flex', 'flex-wrap', 'justify-between')).toBe(true)
    // The bottom bar's links are still an icon over a label, in a row that shares the width.
    const link = within(phoneNav()).getByRole('link', { name: EN['nav.map'].text })
    expect(has(link, 'flex', 'flex-col', 'min-h-tap')).toBe(true)
    expect(has(link.parentElement as HTMLElement, 'flex-1')).toBe(true)
  })

  it('is a grid at lg: the top bar, the notices, the screen and the screen line, in four rows', () => {
    renderApp({ apiUrl: '' })

    // One column that may shrink below its content: every child spans the whole width, so there are no side tracks.
    expect(has(shell(), 'lg:grid', 'lg:grid-cols-[minmax(0,1fr)]', 'lg:grid-rows-[auto_auto_minmax(0,1fr)_auto]')).toBe(true)
    expect(shell().className).not.toContain('lg:grid-cols-[auto_')
    // The header is the first row, across the grid, and one box of its own (the brand navy is its background, see 'the
    // brand top bar'): the brand, then the header's nav, which takes the room between, then the language switch. The footer
    // gives its children to the grid; its nav is not displayed from lg, so the screen line is the only thing it gives.
    expect(has(banner(), 'app-bar', 'flex', 'items-center', 'lg:col-span-full', 'lg:row-start-1', 'lg:flex-nowrap', 'lg:justify-start')).toBe(true)
    expect(banner().classList.contains('lg:contents')).toBe(false)
    expect(has(footer(), 'lg:contents')).toBe(true)
    expect(has(desktopNav(), 'lg:relative', 'lg:z-[1100]', 'lg:flex-1')).toBe(true)
    expect(phoneNav().className).toBe('lg:hidden')
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

  it('gives the top bar\'s nav room for a focus ring around its links, and the screen a ring that its own edge doesn\'t clip', () => {
    renderApp()
    expect(has(desktopNav(), 'lg:py-2')).toBe(true)
    expect(desktopNav().classList.contains('lg:py-1')).toBe(false)
    cleanup()

    // The screen reaches the window's edges at lg, so its ring is drawn inside its box, on the map's screen as on the rest.
    for (const hash of ['#/about', '#/map']) {
      renderApp({ hash })
      expect(screen.getByRole('main').classList.contains('lg:focus-visible:-outline-offset-3'), hash).toBe(true)
      cleanup()
    }
  })

  it('draws the nav as a row of icon and label from lg, each link with the same current-page underline', () => {
    renderApp()

    const link = within(desktopNav()).getByRole('link', { name: EN['nav.map'].text })
    expect(has(link, 'lg:flex-row', 'lg:gap-2', 'lg:px-3')).toBe(true)
    expect(has(link.parentElement as HTMLElement, 'lg:flex-none')).toBe(true)
    expect(link.className).toContain('aria-[current=page]:underline')
    expect(link.getAttribute('aria-current')).toBe('page')
  })
})

// ---- the brand top bar ----
//
// The header is the brand navy (--lusot-brand-navy) at both widths, carrying the owner's L mark and the "Lusot" wordmark,
// with the nav and the language switch in the brand's pale colours, which hold 4.5:1 on the navy (styles/contrast.test.ts).
// jsdom applies no stylesheet, so these pin the classes; the colours themselves are checked on the page by
// e2e/a11y.spec.ts and e2e/desktop.spec.ts (axe's colour contrast).
describe('the brand top bar', () => {
  const banner = () => screen.getByRole('banner')
  const dOf = (svg: string) => [...svg.matchAll(/\sd="([^"]+)"/g)].map((match) => match[1])

  it("draws the owner's L mark before the wordmark, hidden from screen readers, as the master's own paths", () => {
    renderApp()

    const mark = banner().querySelector('svg[data-brand-mark]')
    expect(mark).not.toBeNull()
    expect(mark?.getAttribute('aria-hidden')).toBe('true')
    expect(mark?.getAttribute('focusable')).toBe('false')
    expect(mark?.querySelector('title')).toBeNull()
    expect(Boolean((mark as Node).compareDocumentPosition(within(banner()).getByText('Lusot')) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true)
    // The drawing is brand/lusot-mark.svg's, path for path, so the two can't drift (the boot screen in index.html is held
    // to the same master by loadingScreen.test.ts).
    expect(dOf(mark?.outerHTML ?? '')).toEqual(dOf(masterMark))
  })

  it('sets the wordmark and the header nav in the brand\'s pale colours, which the navy can hold', () => {
    renderApp()

    expect(within(banner()).getByText('Lusot').classList.contains('text-brand-pale')).toBe(true)
    const nav = within(banner()).getByRole('navigation', { hidden: true })
    for (const link of within(nav).getAllByRole('link', { hidden: true })) {
      expect(link.classList.contains('text-brand-mist'), link.textContent ?? '').toBe(true)
      expect(link.className, link.textContent ?? '').toContain('aria-[current=page]:text-brand-pale')
      expect(link.className, link.textContent ?? '').toContain('aria-[current=page]:decoration-brand-water')
    }
  })

  it('leaves the phone\'s bar of tabs on the page\'s own colours, not the brand\'s', () => {
    renderApp()

    const footerNav = within(document.querySelector('footer') as HTMLElement).getByRole('navigation')
    for (const link of within(footerNav).getAllByRole('link')) {
      expect(link.className).not.toContain('brand')
      expect(link.className).toContain('aria-[current=page]:text-action')
    }
  })

  it('sets the language switch on the navy, the chosen language filled in pale with navy text', () => {
    renderApp()

    const group = within(banner()).getByRole('group')
    for (const button of within(group).getAllByRole('button')) {
      expect(button.className).toContain('border-brand-dim')
      expect(button.className).toContain('text-brand-pale')
      expect(button.className).toContain('aria-pressed:bg-brand-pale')
      expect(button.className).toContain('aria-pressed:text-brand-navy')
      expect(button.className).not.toContain('border-outline')
    }
  })

  it('keeps the page\'s own language switch, on About, on the page\'s colours', () => {
    renderApp({ hash: '#/about' })

    const switches = screen.getAllByRole('group', { name: EN['lang.switch'].text })
    const onPage = switches.filter((group) => !banner().contains(group))
    expect(onPage).toHaveLength(1)
    for (const button of within(onPage[0]).getAllByRole('button')) expect(button.className).not.toContain('brand')
  })
})
