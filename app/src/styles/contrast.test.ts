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
