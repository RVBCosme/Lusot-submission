import { describe, expect, it } from 'vitest'
import { CONTRAST_PAIRS, contrastRatio, tokenBlocks } from './contrast'
import tokensCss from './tokens.css?raw'

const blocks = tokenBlocks(tokensCss)

// The three places tokens.css holds colours (C624): light is the default, dark follows the system setting, and
// the person's own choice on About sets data-theme on <html>.
const LIGHT = ':root, :root[data-theme="light"]'
const DARK_SYSTEM = ':root:not([data-theme="light"])'
const DARK_CHOSEN = ':root[data-theme="dark"]'

const themes = { light: blocks[LIGHT], dark: blocks[DARK_SYSTEM] }

describe('contrastRatio', () => {
  it("gives WCAG's ratios: 21 for black on white, 1 for a colour on itself, the same either way round", () => {
    expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 5)
    expect(contrastRatio('#FFFFFF', '#000000')).toBeCloseTo(21, 5)
    expect(contrastRatio('#16181A', '#16181A')).toBe(1)
  })

  it('gives the spec\'s 17.2:1 for gauge ink on pole white', () => {
    expect(contrastRatio('#16181A', '#FBFBF8')).toBeCloseTo(17.17, 2)
  })

  it('reads lower-case hex, and refuses anything that is not a 6-digit hex colour', () => {
    expect(contrastRatio('#fbfbf8', '#16181a')).toBeCloseTo(17.17, 2)
    for (const bad of ['', 'red', '#FFF', '#GGGGGG', 'FFFFFF', '#FFFFFFFF']) {
      expect(() => contrastRatio(bad, '#000000'), bad).toThrow()
    }
  })
})

describe('the token pairs', () => {
  it('cover the pairs C624 names: 4 text pairs at 4.5 and 3 non-text pairs at 3', () => {
    const summary = CONTRAST_PAIRS.map((pair) => [pair.fg, pair.bg, pair.min])
    expect(summary).toEqual([
      ['--lusot-text', '--lusot-surface', 4.5],
      ['--lusot-text-2', '--lusot-surface', 4.5],
      ['--lusot-action', '--lusot-surface', 4.5],
      ['--lusot-on-action', '--lusot-action', 4.5],
      ['--lusot-outline', '--lusot-surface', 3],
      ['--lusot-focus', '--lusot-surface', 3],
      ['--lusot-action', '--lusot-surface', 3],
    ])
  })

  describe.each(Object.entries(themes))('in the %s theme', (_theme, tokens) => {
    it.each(CONTRAST_PAIRS.map((pair) => [pair.name, pair] as const))('%s', (_name, pair) => {
      const ratio = contrastRatio(tokens[pair.fg], tokens[pair.bg])
      expect(ratio, `${pair.fg} on ${pair.bg}: ${ratio.toFixed(2)}`).toBeGreaterThanOrEqual(pair.min)
    })
  })

  it('hold in the dark theme chosen on About, as in the one the system gives', () => {
    for (const pair of CONTRAST_PAIRS) {
      const ratio = contrastRatio(blocks[DARK_CHOSEN][pair.fg], blocks[DARK_CHOSEN][pair.bg])
      expect(ratio, pair.name).toBeGreaterThanOrEqual(pair.min)
    }
  })
})

// The brand colours on the logo's navy (the loading screen in index.html, the splash screens): text holds 4.5:1
// (WCAG 1.4.3), the loading bar's fill holds 3:1 (1.4.11). The bar's track and the waves are decoration, which the
// artwork keeps faint, so they have no pair.
describe('the brand colours on the navy', () => {
  const brand = blocks[':root']
  const TEXT = ['--lusot-brand-pale', '--lusot-brand-mist', '--lusot-brand-dim']

  it.each(TEXT)('%s text holds 4.5:1', (name) => {
    const ratio = contrastRatio(brand[name], brand['--lusot-brand-navy'])
    expect(ratio, `${name} on the navy: ${ratio.toFixed(2)}`).toBeGreaterThanOrEqual(4.5)
  })

  it("the loading bar's fill (the logo's water blue) holds 3:1", () => {
    expect(contrastRatio(brand['--lusot-brand-water'], brand['--lusot-brand-navy'])).toBeGreaterThanOrEqual(3)
  })
})

// The depth fills (C624; Task 3's review, S5-R6). The gauge is the one place that uses them, and it can't lean on a
// fill alone, so these pairs record what the ramp can and can't hold. If a token moves, the lists below fail, and the
// gauge's design is looked at again before they are changed.
describe('the depth fills', () => {
  const STEPS = [1, 2, 3, 4, 5, 6, 7, 8, 9]
  const fill = (tokens: Record<string, string>, step: number) => tokens[`--lusot-depth-${step}`]
  const stepsBelow = (tokens: Record<string, string>, against: string, min: number) =>
    STEPS.filter((step) => contrastRatio(fill(tokens, step), tokens[against]) < min)
  // The best a level name can do on a fill: ink or the page's own colour, whichever is stronger.
  const bestText = (tokens: Record<string, string>, step: number) =>
    Math.max(
      contrastRatio(tokens['--lusot-text'], fill(tokens, step)),
      contrastRatio(tokens['--lusot-surface'], fill(tokens, step)),
    )

  it('in light, steps 1 to 4 fall below 3:1 against the surface and 7 to 9 against the outline', () => {
    expect(stepsBelow(themes.light, '--lusot-surface', 3)).toEqual([1, 2, 3, 4])
    expect(stepsBelow(themes.light, '--lusot-outline', 3)).toEqual([7, 8, 9])
  })

  it('in dark, steps 1 to 3 fall below 3:1 against the surface and 6 to 9 against the outline', () => {
    expect(stepsBelow(themes.dark, '--lusot-surface', 3)).toEqual([1, 2, 3])
    expect(stepsBelow(themes.dark, '--lusot-outline', 3)).toEqual([6, 7, 8, 9])
  })

  it('so a cell is told from the page by its edge, which holds 3:1 against the surface, and never by its fill alone', () => {
    for (const [theme, tokens] of Object.entries(themes)) {
      expect(contrastRatio(tokens['--lusot-outline'], tokens['--lusot-surface']), theme).toBeGreaterThanOrEqual(3)
    }
  })

  it('and the mark on the reading sits on the surface, in the text colour, which holds 4.5:1 there', () => {
    for (const [theme, tokens] of Object.entries(themes)) {
      expect(contrastRatio(tokens['--lusot-text'], tokens['--lusot-surface']), theme).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('only the dark theme\'s step 4 can\'t hold 4.5:1 text, in ink or in the surface colour', () => {
    const failing = (tokens: Record<string, string>) => STEPS.filter((step) => bestText(tokens, step) < 4.5)
    expect(failing(themes.light)).toEqual([])
    expect(failing(themes.dark)).toEqual([4])
  })
})
