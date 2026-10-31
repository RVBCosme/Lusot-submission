import { describe, expect, it } from 'vitest'

// Every text link, and the result card's Details disclosure, is a whole 48 x 48 px target (C625). A link class sets its height with min-h-tap; Task 18's
// end-to-end target check found the short ones ("Map", "Tested") 31 px wide, so each also sets min-w-tap. jsdom
// can't measure a box, so this reads the class strings in app/src. The pattern is put together from pieces, so this
// file doesn't match itself.
const sources = import.meta.glob<string>('./**/*.tsx', { query: '?raw', import: 'default', eager: true })
// A text link's class: min-h-tap, then (after other utilities) text-action followed by underline.
const LINK_CLASS = new RegExp(['min-h-tap', '[^\'"`]*', 'text-action underline'].join(''), 'g')

describe('text links are 48 px wide at least', () => {
  it('finds the link classes it checks', () => {
    const found = Object.values(sources).flatMap((text) => text.match(LINK_CLASS) ?? [])
    expect(found.length).toBeGreaterThanOrEqual(10)
  })

  const withLinks = Object.entries(sources).filter(([, text]) => (text.match(LINK_CLASS) ?? []).length > 0)
  it.each(withLinks)('%s: every link class sets min-w-tap', (_, text) => {
    for (const found of text.match(LINK_CLASS) ?? []) expect(found).toContain('min-w-tap')
  })
})
