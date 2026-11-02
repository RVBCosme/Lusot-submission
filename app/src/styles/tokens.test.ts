import { describe, expect, it } from 'vitest'
import indexHtml from '../../index.html?raw'
import indexCss from '../index.css?raw'
import mainSource from '../main.tsx?raw'
import { tokenBlocks } from './contrast'
import tokensCss from './tokens.css?raw'

const blocks = tokenBlocks(tokensCss)

const LIGHT = ':root, :root[data-theme="light"]'
const DARK_SYSTEM = ':root:not([data-theme="light"])'
const DARK_CHOSEN = ':root[data-theme="dark"]'
const SHARED = ':root'

// Spec §8, direction A (Panukat), as MS5's brief gives it. A change to a colour is a change to this table too.
const LIGHT_COLOURS: Record<string, string> = {
  '--lusot-surface': '#FBFBF8',
  '--lusot-text': '#16181A',
  '--lusot-text-2': '#50565C',
  '--lusot-action': '#0050B3',
  '--lusot-on-action': '#FFFFFF',
  '--lusot-outline': '#16181A',
  '--lusot-focus': '#0050B3',
  '--lusot-depth-1': '#EDE8D0',
  '--lusot-depth-2': '#DDD3AE',
  '--lusot-depth-3': '#C9BC8B',
  '--lusot-depth-4': '#B3A46C',
  '--lusot-depth-5': '#9A8A52',
  '--lusot-depth-6': '#7F703E',
  '--lusot-depth-7': '#64582F',
  '--lusot-depth-8': '#4A4124',
  '--lusot-depth-9': '#312B18',
}
const DARK_COLOURS: Record<string, string> = {
  '--lusot-surface': '#111315',
  '--lusot-text': '#F1F1EC',
  '--lusot-text-2': '#A9AFB5',
  '--lusot-action': '#6EA8FF',
  '--lusot-on-action': '#111315',
  '--lusot-outline': '#F1F1EC',
  '--lusot-focus': '#6EA8FF',
  '--lusot-depth-1': '#3A3626',
  '--lusot-depth-2': '#4E4831',
  '--lusot-depth-3': '#655D3E',
  '--lusot-depth-4': '#7D734C',
  '--lusot-depth-5': '#968A5C',
  '--lusot-depth-6': '#AFA26E',
  '--lusot-depth-7': '#C6BA84',
  '--lusot-depth-8': '#DACF9E',
  '--lusot-depth-9': '#ECE4BE',
}

const depthSteps = (colours: Record<string, string>) => [1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => colours[`--lusot-depth-${n}`])

// The WCAG relative luminance, and the hue in degrees, of a #RRGGBB colour.
function channels(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number]
}
function luminance(hex: string): number {
  const [r, g, b] = channels(hex).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
function hue(hex: string): number {
  const [r, g, b] = channels(hex)
  const max = Math.max(r, g, b)
  const range = max - Math.min(r, g, b)
  const sector = max === r ? ((g - b) / range) % 6 : max === g ? (b - r) / range + 2 : (r - g) / range + 4
  return (sector * 60 + 360) % 360
}

describe('the colour tokens', () => {
  it('hold direction A\'s light values, verbatim', () => {
    expect(blocks[LIGHT]).toMatchObject(LIGHT_COLOURS)
  })

  it('hold direction A\'s dark values, verbatim, when the system is dark and the person has not chosen light', () => {
    expect(blocks[DARK_SYSTEM]).toMatchObject(DARK_COLOURS)
  })

  it('hold the same dark values when the person chooses dark on About', () => {
    expect(blocks[DARK_CHOSEN]).toEqual(blocks[DARK_SYSTEM])
  })

  it('are the same 16 names in both themes, and each theme tells the browser its colour scheme', () => {
    const colourNames = (block: Record<string, string>) => Object.keys(block).filter((name) => name !== 'color-scheme')
    expect(colourNames(blocks[LIGHT]).sort()).toEqual(Object.keys(LIGHT_COLOURS).sort())
    expect(colourNames(blocks[DARK_SYSTEM]).sort()).toEqual(Object.keys(DARK_COLOURS).sort())
    expect(blocks[LIGHT]['color-scheme']).toBe('light')
    expect(blocks[DARK_SYSTEM]['color-scheme']).toBe('dark')
    expect(blocks[DARK_CHOSEN]['color-scheme']).toBe('dark')
  })

  it('make depth one hue that grows stronger with depth, never traffic-light colours (C624)', () => {
    // Stronger is darker on the light page and brighter on the dark one.
    for (const [theme, selector, stronger] of [
      ['light', LIGHT, -1],
      ['dark', DARK_SYSTEM, 1],
    ] as const) {
      const steps = depthSteps(blocks[selector])
      expect(steps, theme).toHaveLength(9)
      const lum = steps.map(luminance)
      for (let i = 1; i < lum.length; i++) {
        expect((lum[i] - lum[i - 1]) * stronger, `${theme}, step ${i} to ${i + 1}`).toBeGreaterThan(0)
      }
      const hues = steps.map(hue)
      expect(Math.max(...hues) - Math.min(...hues), `${theme} hue spread`).toBeLessThan(10)
    }
  })
})

// The owner's logo artwork (app/brand/Lusot-Logo.png) and loading-screen mock, sampled as the median of solid regions,
// never of an anti-aliased edge. They sit in the shared :root block, because the brand does not change with the theme:
// the icons, the splash screens and the loading screen are navy whichever theme the person uses.
const BRAND_COLOURS: Record<string, string> = {
  '--lusot-brand-navy': '#041A3A',
  '--lusot-brand-pale': '#E1F4FE',
  '--lusot-brand-water': '#0A8BFE',
  '--lusot-brand-mist': '#AFCEF3',
  '--lusot-brand-dim': '#82A5D0',
  '--lusot-brand-line': '#183862',
  '--lusot-brand-wave': '#0F3158',
}

describe('the brand tokens', () => {
  it("hold the logo artwork's colours, in the shared block and in neither theme's", () => {
    expect(blocks[SHARED]).toMatchObject(BRAND_COLOURS)
    for (const selector of [LIGHT, DARK_SYSTEM, DARK_CHOSEN]) {
      for (const name of Object.keys(BRAND_COLOURS)) expect(blocks[selector], `${selector} ${name}`).not.toHaveProperty(name)
    }
  })

  it('reach Tailwind as colours, like every other token', () => {
    const theme = indexCss.match(/@theme inline\s*\{([^}]*)\}/)?.[1] ?? ''
    for (const name of Object.keys(BRAND_COLOURS)) {
      expect(theme, name).toContain(`--color-${name.replace('--lusot-', '')}: var(${name});`)
    }
  })
})

describe('the type and spacing tokens', () => {
  const shared = blocks[SHARED]

  it('set the bundled font first, with a system fallback behind it', () => {
    expect(shared['--lusot-font']).toMatch(/^'Atkinson Hyperlegible Next', .*sans-serif$/)
  })

  it('keep a touch target at 48 px or more, and the type in rem so it follows the system text size', () => {
    expect(shared['--lusot-tap']).toBe('3rem')
    for (const name of ['--lusot-type-small', '--lusot-type-body', '--lusot-type-heading', '--lusot-type-title']) {
      expect(shared[name], name).toMatch(/^[\d.]+rem$/)
    }
    expect(parseFloat(shared['--lusot-type-small'])).toBeGreaterThanOrEqual(0.875)
  })
})

describe('Tailwind reads the tokens', () => {
  it('index.css imports them and maps every colour, type and spacing token into @theme', () => {
    expect(indexCss).toMatch(/@import\s+["']\.\/styles\/tokens\.css["']/)
    const theme = indexCss.match(/@theme inline\s*\{([^}]*)\}/)?.[1] ?? ''
    for (const name of [...Object.keys(LIGHT_COLOURS), ...Object.keys(blocks[SHARED])]) {
      expect(theme, name).toContain(`var(${name})`)
    }
  })

  it('index.css keeps its own colours out: every colour lives in tokens.css', () => {
    expect(indexCss).not.toMatch(/#[0-9a-fA-F]{3,8}\b|\b(rgb|hsl|oklch)a?\(/)
  })

  it('index.css draws a visible focus ring from the focus token', () => {
    expect(indexCss).toMatch(/:focus-visible\s*\{[^}]*var\(--lusot-focus\)/)
  })

  it('index.css stops animations and transitions under prefers-reduced-motion: reduce (C625)', () => {
    const rule = indexCss.match(/@media \(prefers-reduced-motion: reduce\)\s*\{([\s\S]*?)\n\}/)?.[1] ?? ''
    expect(rule).toMatch(/animation-duration:\s*0\.01ms\s*!important/)
    expect(rule).toMatch(/transition-duration:\s*0\.01ms\s*!important/)
  })
})

describe('fonts are bundled (C623)', () => {
  it('main.tsx imports the two weights from @fontsource, and nothing asks Google Fonts or a CDN', () => {
    expect(mainSource).toContain("import '@fontsource/atkinson-hyperlegible-next/400.css'")
    expect(mainSource).toContain("import '@fontsource/atkinson-hyperlegible-next/700.css'")
    for (const [name, source] of [['index.html', indexHtml], ['index.css', indexCss], ['tokens.css', tokensCss]]) {
      expect(source, name).not.toMatch(/fonts\.googleapis|fonts\.gstatic|cdn\./i)
      expect(source, name).not.toMatch(/@import\s+url\(|https?:\/\//)
    }
  })
})

describe('no component holds a colour of its own', () => {
  // Every component and screen takes its colours from the tokens, through Tailwind's utilities, so a different
  // direction is a change to tokens.css alone (MS5-Q1). Tests and the test setup aren't components.
  const sources = import.meta.glob<string>('../**/*.tsx', { query: '?raw', import: 'default', eager: true })
  const components = Object.entries(sources).filter(([path]) => !/\.test\.tsx$|\/test\//.test(path))

  // Tailwind's own palette (bg-neutral-300, text-white, ...), a hex or functional colour, or an arbitrary value
  // that carries a colour or a length in px or rem (text-[#abc], p-[13px]).
  const PALETTE =
    /\b(?:bg|text|border|ring|outline|fill|stroke|from|via|to|divide|decoration|accent|caret|shadow|placeholder)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)\b/
  const LITERAL = /#[0-9a-fA-F]{3,8}\b|\b(?:rgb|hsl|oklch)a?\(|-\[[^\]]*(?:#|\d(?:px|rem|em)\b)/

  it('finds the components it checks', () => {
    expect(components.length).toBeGreaterThan(10)
  })

  it.each(components)('%s', (_path, source) => {
    expect(source).not.toMatch(PALETTE)
    expect(source).not.toMatch(LITERAL)
  })
})
