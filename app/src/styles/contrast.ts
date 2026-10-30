// The contrast check (C624, C625): WCAG 2.2's ratio between two colours, the token pairs that must clear it, and a
// reader for tokens.css, so a test checks the colours the app ships and not a copy of them. Nothing in the app's
// screens imports this file, so the build leaves it out.

// The ratio of two #RRGGBB colours, from 1 to 21, whichever comes first (WCAG 2.2, relative luminance).
export function contrastRatio(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

function luminance(hex: string): number {
  if (!/^#[0-9a-fA-F]{6}$/.test(hex)) throw new Error(`Not a #RRGGBB colour: ${JSON.stringify(hex)}`)
  const [r, g, b] = [1, 3, 5].map((start) => {
    const channel = parseInt(hex.slice(start, start + 2), 16) / 255
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export type ContrastPair = {
  name: string
  // The tokens, as tokens.css names them.
  fg: string
  bg: string
  // 4.5 for text (WCAG 1.4.3), 3 for a meaningful part of the interface (1.4.11).
  min: 4.5 | 3
}

// Text is always on the surface, because the depth fills can't hold 4.5:1 text in either colour (C624); the
// outline, not the fill, carries a gauge cell. The action colour is both link text and a button's fill, so it is
// held to both.
export const CONTRAST_PAIRS: readonly ContrastPair[] = [
  { name: 'text on the surface', fg: '--lusot-text', bg: '--lusot-surface', min: 4.5 },
  { name: 'secondary text on the surface', fg: '--lusot-text-2', bg: '--lusot-surface', min: 4.5 },
  { name: 'action as link text on the surface', fg: '--lusot-action', bg: '--lusot-surface', min: 4.5 },
  { name: 'text on an action fill', fg: '--lusot-on-action', bg: '--lusot-action', min: 4.5 },
  { name: 'the outline against the surface', fg: '--lusot-outline', bg: '--lusot-surface', min: 3 },
  { name: 'the focus ring against the surface', fg: '--lusot-focus', bg: '--lusot-surface', min: 3 },
  { name: 'an action fill against the surface', fg: '--lusot-action', bg: '--lusot-surface', min: 3 },
]

// The declarations of each innermost rule in a stylesheet, keyed by its selector with the whitespace tidied to
// one space after each comma. A rule inside @media is found by its own selector. A variable's value is kept as
// written, so a test reads the file's colours exactly.
export function tokenBlocks(css: string): Record<string, Record<string, string>> {
  const blocks: Record<string, Record<string, string>> = {}
  const rules = css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^{}]*)\}/g)
  for (const [, selector, body] of rules) {
    const key = selector.trim().replace(/\s*,\s*/g, ', ').replace(/\s+/g, ' ')
    const declarations: Record<string, string> = (blocks[key] ??= {})
    for (const declaration of body.split(';')) {
      const colon = declaration.indexOf(':')
      if (colon > 0) declarations[declaration.slice(0, colon).trim()] = declaration.slice(colon + 1).trim()
    }
  }
  return blocks
}
