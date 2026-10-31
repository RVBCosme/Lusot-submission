import { describe, expect, it } from 'vitest'

// The development mock reaches a build only through app/src/lib/apiFetch.ts, whose `import.meta.env.DEV` guard lets a
// production build drop it. The bundle check looks for the marker that mockFetch puts on its answers, so a screen that
// imported a fixture or the drawing code directly would ship that data with no marker, and the check would pass.
// Only apiFetch.ts, and test files and the test setup, may import from app/src/mock/. This reads every source file as
// text and looks at its relative import specifiers: static imports, `import()` and re-exports.

const ALLOWED = ['lib/apiFetch.ts']

// Where this file's own folder sits under app/src, so a glob key (relative to it) becomes a path under app/src.
const HERE = 'mock'

function normalise(path: string): string {
  const parts: string[] = []
  for (const part of path.split('/')) {
    if (part === '..') parts.pop()
    else if (part !== '.' && part !== '') parts.push(part)
  }
  return parts.join('/')
}

const RELATIVE_SPECIFIER = /\b(?:from|import)\s*\(?\s*(['"])(\.{1,2}\/[^'"]+)\1/g

// The files outside app/src/mock/ that import from it. `files` maps a path under app/src to the file's text.
function mockImporters(files: Record<string, string>): string[] {
  const importers: string[] = []
  for (const [path, source] of Object.entries(files)) {
    if (path.startsWith('mock/')) continue
    const folder = path.slice(0, path.lastIndexOf('/') + 1)
    for (const match of source.matchAll(RELATIVE_SPECIFIER)) {
      const target = normalise(`${folder}${match[2]}`)
      if (target === 'mock' || target.startsWith('mock/')) {
        importers.push(path)
        break
      }
    }
  }
  return importers.sort()
}

describe('only apiFetch.ts imports from app/src/mock/', () => {
  const globbed = import.meta.glob<string>('../**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true })
  const files = Object.fromEntries(
    Object.entries(globbed)
      .map(([key, source]) => [normalise(`${HERE}/${key}`), source] as const)
      .filter(([path]) => !/\.test\.tsx?$|^test\//.test(path)),
  )

  it('finds the sources it checks, apiFetch.ts among them', () => {
    expect(Object.keys(files).length).toBeGreaterThan(20)
    expect(Object.keys(files)).toContain('lib/apiFetch.ts')
  })

  it('has no other source file that imports from it', () => {
    expect(mockImporters(files)).toEqual(ALLOWED)
  })

  it('sees an import written any way a screen could write it', () => {
    const found = mockImporters({
      'lib/apiFetch.ts': "import { mockFetch } from '../mock/mockFetch'",
      'screens/Static.tsx': "import { SAMPLES } from '../mock/fixtures'",
      'screens/Multiline.tsx': "import {\n  SAMPLES,\n} from \"../mock/fixtures\"",
      'screens/Dynamic.tsx': "const draw = await import('../mock/draw')",
      'screens/Reexport.tsx': "export * from '../mock/mockFetch'",
      'screens/Bare.tsx': "import '../mock/fixtures'",
      'screens/deep/Deep.tsx': "import { x } from '../../mock/fixtures'",
      'screens/Fine.tsx': "import { apiFetch } from '../lib/apiFetch'\nimport { useState } from 'react'",
      'screens/Elsewhere.tsx': "import { x } from './mock/helper'",
      'mock/Inside.ts': "import { x } from './fixtures'",
    })
    expect(found).toEqual([
      'lib/apiFetch.ts',
      'screens/Bare.tsx',
      'screens/Dynamic.tsx',
      'screens/Multiline.tsx',
      'screens/Reexport.tsx',
      'screens/Static.tsx',
      'screens/deep/Deep.tsx',
    ])
  })
})
