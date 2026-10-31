import { afterEach, expect, it, vi } from 'vitest'
import mainSource from '../main.tsx?raw'
import { HttpError } from './api'
import { errorClass, rootErrorOptions } from './rootErrors'

const ID = 'r_0123456789abcdef0123456789abcdef'
const INFO = { componentStack: `\n    at PinScreen (#/pin/${ID})` }

afterEach(() => {
  vi.restoreAllMocks()
})

it('errorClass names the kind of error and nothing it carries', () => {
  expect(errorClass(new HttpError(404, 'not_found', `no report ${ID}`))).toBe('HttpError')
  expect(errorClass(new TypeError(`bad ${ID}`))).toBe('TypeError')
  // A name that isn't a plain class name could carry anything.
  const renamed = new Error('x')
  renamed.name = `Error ${ID}`
  expect(errorClass(renamed)).toBe('Error')
  expect(errorClass(ID)).toBe('string')
  expect(errorClass({ lat: 14.6, lng: 121.0 })).toBe('object')
  expect(errorClass(null)).toBe('null')
})

it.each(['onCaughtError', 'onUncaughtError', 'onRecoverableError'] as const)(
  '%s logs the error class only: no message, report id, position or component stack',
  (name) => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    const others = (['log', 'warn', 'info', 'debug'] as const).map((method) =>
      vi.spyOn(console, method).mockImplementation(() => {}),
    )

    rootErrorOptions[name](new HttpError(500, 'internal', `report ${ID} at 14.6123, 121.0456`), INFO)

    expect(log).toHaveBeenCalledOnce()
    const logged = log.mock.calls[0]?.map(String).join(' ') ?? ''
    expect(logged).toContain('HttpError')
    expect(logged).not.toMatch(/r_[0-9a-f]|14\.6|121\.0|internal|PinScreen|at /)
    for (const spy of others) expect(spy).not.toHaveBeenCalled()
  },
)

it("the app's root is made with these options", () => {
  expect(mainSource).toMatch(/createRoot\(document\.getElementById\('root'\)!, rootErrorOptions\)/)
})
