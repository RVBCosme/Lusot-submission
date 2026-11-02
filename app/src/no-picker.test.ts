import { describe, expect, it } from 'vitest'
import packageJson from '../package.json?raw'

// A photo enters the app by the in-app camera's stream (C602), and by one more way: a photo the person chooses on the
// Tested page, whose one file input is in TryPhoto.tsx (C640). No other file input, no gallery and no camera plugin
// exists anywhere under app/src. Every pattern, and every sample it is tried on, is put together here from pieces, so
// this file doesn't match itself.
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

// The one file that may hold the file input (patterns 0 and 1), once.
const TRY_PHOTO = './components/TryPhoto.tsx'
const FILE_INPUT_PATTERNS = PATTERNS.slice(0, 2)
const OTHER_PATTERNS = PATTERNS.slice(2)

const filesHolding = (pattern: RegExp) =>
  Object.entries(sources)
    .filter(([, source]) => pattern.test(source))
    .map(([path]) => path)

describe('no way to pick a photo but the Tested page', () => {
  it('reads the app sources it checks', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(40)
    expect(Object.keys(sources)).toContain('./screens/report/CameraStep.tsx')
    expect(Object.keys(sources)).toContain(TRY_PHOTO)
  })

  it.each(OTHER_PATTERNS)('no file under src holds %s, TryPhoto.tsx included', (_name, pattern) => {
    expect(filesHolding(pattern)).toEqual([])
  })

  it('only TryPhoto.tsx holds a file input, and it holds exactly one', () => {
    for (const [name, pattern] of FILE_INPUT_PATTERNS) expect(filesHolding(pattern).filter((path) => path !== TRY_PHOTO), name).toEqual([])
    const inputs = FILE_INPUT_PATTERNS.reduce(
      (count, [, pattern]) => count + (sources[TRY_PHOTO]?.match(new RegExp(pattern.source, 'g')) ?? []).length,
      0,
    )
    expect(inputs).toBe(1)
  })

  it('TryPhoto.tsx sends a chosen photo through POST /try only: no requestUpload and no /uploads', () => {
    expect(sources[TRY_PHOTO]).toBeDefined()
    expect(sources[TRY_PHOTO]).not.toContain('requestUpload')
    expect(sources[TRY_PHOTO]).not.toContain('/uploads')
  })

  it('nothing in the camera Report flow imports TryPhoto', () => {
    // The screens, the flow's reducer and its provider (./report/), and the Report screen itself.
    const flow = Object.entries(sources).filter(
      ([path]) =>
        path.startsWith('./screens/report/') || path.startsWith('./report/') || path === './screens/ReportScreen.tsx',
    )
    expect(flow.map(([path]) => path)).toContain('./report/ReportFlowProvider.tsx')
    expect(flow.length).toBeGreaterThan(5)
    for (const [path, source] of flow) expect(source, path).not.toContain('TryPhoto')
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
