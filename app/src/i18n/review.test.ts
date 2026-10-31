import { expect, it } from 'vitest'
import { unreviewedKeys } from './index'

// The copy-review count (C609, M20). `npm run copy:review -w app` prints it; a release build sets
// VITE_LUSOT_RELEASE=1, and then any line still waiting for Rene's review fails the run.
it('counts the lines waiting for review, and fails a release while any remain', () => {
  const unreviewed = unreviewedKeys()
  console.log(
    [`unreviewed lines: ${unreviewed.length}`, ...unreviewed.map(({ lang, key }) => `  ${lang} ${key}`)].join('\n'),
  )
  if (import.meta.env.VITE_LUSOT_RELEASE === '1') expect(unreviewed).toEqual([])
})
