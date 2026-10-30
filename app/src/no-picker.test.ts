import { describe, expect, it } from 'vitest'
import packageJson from '../package.json?raw'

// A photo enters the app one way: the in-app camera's stream (C602). No file input, no gallery and no camera
// plugin exists anywhere under app/src. Every pattern, and every sample it is tried on, is put together here from
// pieces, so this file doesn't match itself.
const sources = import.meta.glob<string>('./**/*.{ts,tsx}', { query: '?raw', import: 'default', eager: true })

const FILE = ['fi', 'le'].join('')
const CAPTURE = ['cap', 'ture'].join('')
const PICKER_API = ['show', 'Open', 'File', 'Picker'].join('')
const GALLERY = ['choose', 'From', 'Gallery'].join('')
const CAMERA_PLUGIN = ['@capacitor', 'camera'].join('/')

const quoted = `(?:"${FILE}"|'${FILE}'|\`${FILE}\`)`
const PATTERNS: [name: string, pattern: RegExp][] = [
  // The input type in markup (in double quotes, single quotes or braces), and the same from script.
  ['a file input', new RegExp(`\\btype\\s*=\\s*(?:${quoted}|\\{\\s*${quoted}\\s*\\})`)],
  ['a file input made in script', new RegExp(`\\.type\\s*=\\s*${quoted}|setAttribute\\(\\s*['"]type['"]\\s*,\\s*${quoted}`)],
  ['the capture attribute', new RegExp(`\\b${CAPTURE}=`)],
  ['the file picker API', new RegExp(PICKER_API)],
  ['a gallery pick', new RegExp(GALLERY)],
  ['the camera plugin', new RegExp(CAMERA_PLUGIN)],
]

describe('no way to pick a photo', () => {
  it('reads the app sources it checks', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(40)
    expect(Object.keys(sources)).toContain('./screens/report/CameraStep.tsx')
  })

  it.each(PATTERNS)('no file under src holds %s', (_name, pattern) => {
    const hits = Object.entries(sources)
      .filter(([, source]) => pattern.test(source))
      .map(([path]) => path)
    expect(hits).toEqual([])
  })

  it("the app's package.json does not list the camera plugin", () => {
    expect(packageJson).not.toContain(CAMERA_PLUGIN)
  })

  // A guard that can't fail guards nothing: each pattern does match what it is for.
  it.each([
    [0, `<input type="${FILE}" />`],
    [0, `<input type='${FILE}' />`],
    [0, `<input type={'${FILE}'} />`],
    [0, `<input type = {"${FILE}"} />`],
    [1, `input.type = '${FILE}'`],
    [1, `input.setAttribute('type', "${FILE}")`],
    [2, `<input ${CAPTURE}="environment" />`],
    [3, `await window.${PICKER_API}()`],
    [4, `${GALLERY}()`],
    [5, `import { Camera } from '${CAMERA_PLUGIN}'`],
  ])('pattern %i matches %s', (index, sample) => {
    expect(PATTERNS[index]?.[1].test(sample)).toBe(true)
  })

  it('and none of them matches a checkbox, a captured time or the Geolocation plugin', () => {
    const fine = `<input type="checkbox" /> capturedAt="x" import { Geolocation } from '@capacitor/geolocation'`
    for (const [, pattern] of PATTERNS) expect(pattern.test(fine)).toBe(false)
  })
})
