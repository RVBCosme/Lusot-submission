import { createElement } from 'react'
import { flushSync } from 'react-dom'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import mark from '../brand/lusot-mark.svg?raw'
import indexHtml from '../index.html?raw'
import { EN } from './i18n/en'
import indexCss from './index.css?raw'
import mainSource from './main.tsx?raw'
import { contrastRatio, tokenBlocks } from './styles/contrast'
import tokensCss from './styles/tokens.css?raw'

// The loading screen in app/index.html: what a person sees from the first byte until the app's own code has run and
// React's first render replaces it. It has to stand alone (inline CSS, an inline mark, an inline script, no request),
// so these tests read the page as text and parse it, then run its script the way a browser would.
const page = new DOMParser().parseFromString(indexHtml, 'text/html')
const appRoot = page.getElementById('root')!
const rootMarkup = appRoot.innerHTML
const style = page.head.querySelector('style')?.textContent ?? ''
const script = appRoot.querySelector('script')?.textContent ?? ''

const TAGLINE = { en: 'Flood depth from photos', fil: 'Lalim ng baha mula sa mga photo' }
const STATUS = { en: 'Loading Lusot…', fil: 'Nilo-load ang Lusot…' }

// The page's markup in a fresh root in the live document, with the script run on it when `run` is set.
function mount(run: boolean): HTMLElement {
  document.body.innerHTML = ''
  const container = document.createElement('div')
  container.id = 'root'
  // Markup set through innerHTML never runs its scripts, as in a parsed page; the script is run on purpose below.
  container.innerHTML = rootMarkup
  document.body.append(container)
  if (run) window.eval(script)
  return container
}

const text = (container: HTMLElement, selector: string) => container.querySelector(selector)?.textContent
const progressbar = (container: HTMLElement) => container.querySelector('[role="progressbar"]')!

// The inline CSS split at its no-preference blocks (found by their braces): what moves, and what is left for everyone
// else, a person who asked for less motion included.
function splitMotion(css: string): { blocks: string; rest: string } {
  const blocks: string[] = []
  let rest = css
  for (;;) {
    const start = rest.indexOf('@media (prefers-reduced-motion: no-preference)')
    if (start === -1) break
    const open = rest.indexOf('{', start)
    let depth = 0
    let end = open
    for (; end < rest.length; end++) {
      if (rest[end] === '{') depth += 1
      else if (rest[end] === '}' && --depth === 0) break
    }
    blocks.push(rest.slice(open + 1, end))
    rest = rest.slice(0, start) + rest.slice(end + 1)
  }
  return { blocks: blocks.join(' '), rest }
}

// The colour of `fg` laid at `alpha` over `bg`, as #RRGGBB.
function over(fg: string, bg: string, alpha: number): string {
  const channel = (start: number) =>
    Math.round(parseInt(fg.slice(start, start + 2), 16) * alpha + parseInt(bg.slice(start, start + 2), 16) * (1 - alpha))
  return '#' + [1, 3, 5].map((start) => channel(start).toString(16).padStart(2, '0')).join('')
}

// The padding a rule of the inline CSS declares, with the spaces made single.
function padding(selector: string): string | undefined {
  const escaped = selector.replace(/[.]/g, '\\.')
  const body = new RegExp(`(?:^|[\\s}])${escaped}\\s*\\{([^}]*)\\}`).exec(style)?.[1]
  return body?.match(/(?:^|;)\s*padding:\s*([^;]+)/)?.[1].replace(/\s+/g, ' ').trim()
}

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  document.body.innerHTML = ''
})

describe('the loading screen, in English', () => {
  it('sits inside the React root, so the first render replaces it, with no delay of its own on the web', () => {
    const container = mount(false)
    expect(container.querySelector('main#boot')).not.toBeNull()
    expect(mainSource).toMatch(/createRoot\(document\.getElementById\('root'\)!/)

    const root = createRoot(container)
    // Making the root leaves the screen in place; only its first render replaces it. That is what lets the APK hold the
    // screen for its five steps (bootHold.ts) before it renders, with the root already made.
    expect(container.querySelector('#boot')).not.toBeNull()
    flushSync(() => root.render(createElement('p', null, 'the app')))
    expect(container.querySelector('#boot')).toBeNull()
    expect(container.querySelector('script')).toBeNull()
    expect(container.textContent).toBe('the app')
    root.unmount()

    // The page's own script waits for nothing: the hold of the APK's cold start is in the app's code (bootHold.ts), and
    // the website renders at once.
    expect(script).not.toMatch(/setTimeout|setInterval|requestAnimationFrame|await|Promise/)
  })

  it('names the product, says what it does, and says it is loading', () => {
    const container = mount(false)
    expect(text(container, 'h1')).toBe('Lusot')
    expect(text(container, '.boot-tagline')).toBe(TAGLINE.en)
    expect(text(container, '.boot-status')).toBe(STATUS.en)
    expect(text(container, '.boot-place')).toBe('Metro Manila')
  })

  it('is busy as a whole, and its indeterminate progress bar takes its name from the status text', () => {
    const container = mount(false)
    expect(container.querySelector('main#boot')?.getAttribute('aria-busy')).toBe('true')
    const bar = progressbar(container)
    expect(bar.hasAttribute('aria-busy')).toBe(false)
    for (const value of ['aria-valuenow', 'aria-valuemin', 'aria-valuemax', 'aria-valuetext']) {
      expect(bar.hasAttribute(value), value).toBe(false)
    }
    const name = document.getElementById(bar.getAttribute('aria-labelledby') ?? '')
    expect(name?.textContent).toBe(STATUS.en)
    expect(name?.classList.contains('boot-status')).toBe(true)
  })

  it('carries the screen line in English, the one the app puts on every screen', () => {
    const line = mount(false).querySelector('.boot-line')
    expect(line?.tagName).toBe('P')
    expect(line?.textContent).toBe(EN['layout.screenLine'].text)
    expect(line?.getAttribute('lang')).toBe('en')
  })

  it("draws the master mark inline, hidden from screen readers, and leaves the rest of the picture to CSS", () => {
    const svg = mount(false).querySelector('.boot-mark')!
    expect(svg.tagName.toLowerCase()).toBe('svg')
    expect(svg.getAttribute('aria-hidden')).toBe('true')
    expect(svg.getAttribute('focusable')).toBe('false')
    // The drawing between <defs> and the last </g>, with the layout whitespace taken out and every tag written the way
    // the page's HTML writes it (<path></path>, not <path/>), is the master's word for word.
    const body = (markup: string) =>
      /<defs>[\s\S]*<\/g>/
        .exec(markup)![0]
        .replace(/>\s+</g, '><')
        .replace(/<(\w+)([^>]*?)\s*\/>/g, '<$1$2></$1>')
    expect(body(svg.innerHTML)).toBe(body(mark))
  })

  it('draws the waves and the bar apart from the text: decoration that screen readers skip', () => {
    const container = mount(false)
    expect(container.querySelector('.boot-waves')?.getAttribute('aria-hidden')).toBe('true')
    // The only things a screen reader reads are the heading, the tagline, the bar by its name, the status and the lines.
    const reads = [...container.querySelectorAll('main *')].filter((el) => el.matches('h1, p, [role="progressbar"]'))
    expect(reads.map((el) => el.className.split(' ')[0] || el.tagName.toLowerCase())).toEqual([
      'boot-name',
      'boot-tagline',
      'boot-bar',
      'boot-status',
      'boot-place',
      'boot-line',
    ])
  })
})

describe('the loading screen, in the language the person chose', () => {
  it('swaps in the approved Taglish lines, marked lang="fil", when the chosen language is Taglish', () => {
    localStorage.setItem('lusot.lang', 'fil')
    const container = mount(true)
    expect(text(container, '.boot-tagline')).toBe(TAGLINE.fil)
    expect(text(container, '.boot-status')).toBe(STATUS.fil)
    expect(container.querySelector('.boot-tagline')?.getAttribute('lang')).toBe('fil')
    expect(container.querySelector('.boot-status')?.getAttribute('lang')).toBe('fil')
    // The bar's name follows the status text, in whichever language, and nothing else changed.
    const name = document.getElementById(progressbar(container).getAttribute('aria-labelledby') ?? '')
    expect(name?.textContent).toBe(STATUS.fil)
    expect(text(container, 'h1')).toBe('Lusot')
    expect(text(container, '.boot-place')).toBe('Metro Manila')
    expect(text(container, '.boot-line')).toBe(EN['layout.screenLine'].text)
    expect(container.querySelector('.boot-line')?.getAttribute('lang')).toBe('en')
  })

  it.each([
    ['no language is kept', () => undefined],
    ['English is kept', () => localStorage.setItem('lusot.lang', 'en')],
    ['something else is kept', () => localStorage.setItem('lusot.lang', 'de')],
  ])('stays in English when %s', (_name, arrange) => {
    arrange()
    const container = mount(true)
    expect(text(container, '.boot-tagline')).toBe(TAGLINE.en)
    expect(text(container, '.boot-status')).toBe(STATUS.en)
    expect(container.querySelector('[lang="fil"]')).toBeNull()
  })

  it('stays in English, and throws nothing, when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError')
    })
    const container = mount(true)
    expect(text(container, '.boot-tagline')).toBe(TAGLINE.en)
    expect(text(container, '.boot-status')).toBe(STATUS.en)
  })
})

describe('the loading screen stands alone', () => {
  // With JavaScript off the screen would say "Loading Lusot…" for ever, so a <noscript> says why, in both languages, since
  // no script can pick one (the tracker's approved wording, Nov 2).
  it('tells a browser without JavaScript that Lusot needs it, in English and Taglish', () => {
    const noscript = /<main[^>]*id="boot"[\s\S]*?<noscript>([\s\S]*?)<\/noscript>[\s\S]*?<\/main>/.exec(indexHtml)?.[1] ?? ''
    expect(noscript).toContain('<p class="boot-noscript" lang="en">Lusot needs JavaScript to run. Please turn it on in your browser.</p>')
    expect(noscript).toContain(
      '<p class="boot-noscript" lang="fil">Kailangan ng Lusot ang JavaScript para gumana. Paki-on ito sa browser mo.</p>',
    )
    // The status line's mist, so it meets AA on the navy like the rest (the token test below checks every colour).
    expect(style).toMatch(/\.boot-noscript\{[^}]*color:#AFCEF3/)
  })

  it('asks for nothing: no request, no external address, no font or file', () => {
    expect(style).not.toMatch(/url\(|@import|https?:|@font-face/)
    expect(rootMarkup).not.toMatch(/https?:|\bsrc=|\bhref=|<img|<link|<use\b|xmlns/)
    expect(script).not.toMatch(/fetch|XMLHttpRequest|import\(|https?:/)
    // The page's own head stays as it was: a manifest, the icons, no stylesheet link or font of its own.
    expect(indexHtml).toMatch(/<link rel="manifest" href="\/manifest\.webmanifest"/)
    expect(indexHtml).toMatch(/<link rel="apple-touch-icon" href="\/icons\/apple-touch-icon\.png"/)
    expect(indexHtml).not.toMatch(/rel="stylesheet"|fonts\./)
  })

  it('moves only for a person with no reduced-motion preference, and holds still for anyone else', () => {
    // Take out every no-preference block, and what is left may not animate or transition.
    const { blocks, rest } = splitMotion(style)
    expect(blocks).not.toBe('')
    expect(blocks).toMatch(/\.boot-fill\s*\{[^}]*animation:/)
    expect(blocks).toMatch(/\.boot-waves svg\s*\{[^}]*animation:/)
    // The sliding piece is a third of the bar, as the artwork's own mock draws it.
    expect(blocks).toMatch(/\.boot-fill\s*\{[^}]*width:\s*36%/)
    expect(rest).not.toMatch(/animation|transition/)
  })

  it('holds still as a dim, full-width fill, never a share of the bar that would read as stuck progress', () => {
    const { rest } = splitMotion(style)
    expect(rest).toMatch(/\.boot-fill\s*\{[^}]*width:\s*100%/)
    expect(rest).not.toContain('36%')
    // The dim fill still holds 3:1 against the navy where it lies on the track (WCAG 1.4.11).
    const alpha = Number(/\.boot-fill\s*\{[^}]*opacity:\s*([\d.]+)/.exec(rest)?.[1])
    expect(alpha).toBeGreaterThan(0)
    expect(alpha).toBeLessThan(1)
    const hex = (selector: string) => new RegExp(`${selector}\\s*\\{[^}]*background:\\s*(#[0-9A-Fa-f]{6})`).exec(rest)![1]
    const brand = tokenBlocks(tokensCss)[':root']
    const dim = over(hex('\\.boot-fill'), hex('\\.boot-bar'), alpha)
    expect(contrastRatio(dim, brand['--lusot-brand-navy'])).toBeGreaterThanOrEqual(3)
  })

  // The APK holds the screen for five steps of 20 % (bootHold.ts), and the class it adds turns the bar determinate: the
  // fill's width is the --boot-progress the hold sets. It steps with no transition for a person who asked for less motion.
  it('has a determinate bar for the APK: the fill takes its width from --boot-progress, in full colour', () => {
    const { rest } = splitMotion(style)
    expect(rest).toMatch(/\.boot-steps \.boot-fill\s*\{[^}]*width:\s*var\(--boot-progress,\s*0%\)[^}]*opacity:\s*1[;}]/)
    // The track and the fill's colours are the indeterminate bar's own.
    expect(rest).not.toMatch(/\.boot-steps[^{]*\{[^}]*background/)
  })

  it('stops the slide for a person with no reduced-motion preference, and eases each step from the second', () => {
    const { blocks, rest } = splitMotion(style)
    expect(blocks).toMatch(/\.boot-steps \.boot-fill\s*\{[^}]*animation:\s*none/)
    // The first step (20 %) shows at once, from the sliding bar's width, so the class that starts the hold has no
    // transition; the one the hold adds with the second step (boot-eased) has it.
    expect(blocks).not.toMatch(/\.boot-steps \.boot-fill\s*\{[^}]*transition/)
    expect(blocks).toMatch(/\.boot-eased \.boot-fill\s*\{[^}]*transition:\s*width\s+[\d.]+m?s/)
    // Anyone else gets each step at once: nothing outside the no-preference blocks moves (also checked above).
    expect(rest).not.toMatch(/transition|boot-eased/)
  })

  it("is painted in the brand tokens' colours and no others", () => {
    const brand = new Set(
      Object.entries(tokenBlocks(tokensCss)[':root'])
        .filter(([name]) => name.startsWith('--lusot-brand-'))
        .map(([, value]) => value.toUpperCase()),
    )
    const used = [...(style + rootMarkup).matchAll(/#[0-9A-Fa-f]{6}\b/g)].map((m) => m[0].toUpperCase())
    expect(used.length).toBeGreaterThan(5)
    for (const colour of used) expect(brand.has(colour), `${colour} is a brand token`).toBe(true)
  })

  it('covers the screen on its own navy, so no theme or unloaded style shows round it', () => {
    expect(style).toMatch(/\.boot\s*\{[^}]*position:\s*fixed[^}]*inset:\s*0/)
    expect(style).toMatch(/\.boot\s*\{[^}]*background:\s*#041A3A/i)
    // It never touches the page's own background, which belongs to the theme.
    expect(style).not.toMatch(/(^|[\s,}])(html|body|:root)\s*[,{]/)
  })

  it('keeps its script in a function of its own, so `lines` and `i` never become globals', () => {
    expect(script.trim()).toMatch(/^\(function\s*\(\)\s*\{[\s\S]*\}\)\(\);?$/)
    for (const language of [null, 'fil']) {
      Reflect.deleteProperty(window, 'lines')
      Reflect.deleteProperty(window, 'i')
      if (language) localStorage.setItem('lusot.lang', language)
      mount(true)
      expect('lines' in window, `lines, language ${language}`).toBe(false)
      expect('i' in window, `i, language ${language}`).toBe(false)
    }
  })

  it('says what the page really waits for: the render-blocking stylesheet, then the code that replaces the screen', () => {
    // The comment just above the <style> element.
    const styleAt = indexHtml.indexOf('<style>')
    const comment = indexHtml.slice(indexHtml.lastIndexOf('<!--', styleAt), styleAt)
    expect(comment).toContain("loading screen's styles")
    expect(comment).not.toMatch(/before any file has loaded/)
    expect(comment).toMatch(/render-blocking stylesheet/)
  })
})

describe('the loading screen clears the system bars', () => {
  // The app shell's mechanism (.safe-area in index.css): Capacitor 8 injects --safe-area-inset-* on Android, where
  // env(safe-area-inset-*) is wrong in WebViews before Chromium 140, and a browser falls back to env().
  const inset = (side: string) => `var(--safe-area-inset-${side}, env(safe-area-inset-${side}, 0px))`

  it('uses the same inset expressions as the app shell', () => {
    for (const side of ['top', 'bottom']) expect(indexCss).toContain(inset(side))
  })

  it('adds the top inset to the padding above the mark, and the bottom inset to the padding below the screen line', () => {
    expect(padding('.boot-centre')).toBe(`calc(2rem + ${inset('top')}) 1.5rem 2rem`)
    expect(padding('.boot-foot')).toBe(`1rem 1.5rem calc(1.5rem + ${inset('bottom')})`)
  })
})
