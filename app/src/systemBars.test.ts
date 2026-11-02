import { Capacitor, SystemBars } from '@capacitor/core'
import { afterEach, describe, expect, it, vi } from 'vitest'
import mainSource from './main.tsx?raw'
import { styleStatusBar } from './systemBars'

// The module is mocked down to the two calls the file makes; the enums stay Capacitor's own, so a typo in a style or a bar
// would fail here as it would on a phone.
vi.mock('@capacitor/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@capacitor/core')>()
  return {
    ...actual,
    Capacitor: { ...actual.Capacitor, isNativePlatform: vi.fn(() => false) },
    SystemBars: { setStyle: vi.fn(async () => {}) },
  }
})

const native = (on: boolean) => vi.mocked(Capacitor.isNativePlatform).mockReturnValue(on)

afterEach(() => {
  vi.mocked(SystemBars.setStyle).mockReset()
  vi.mocked(SystemBars.setStyle).mockResolvedValue(undefined)
  native(false)
})

// The header is navy at both widths and under the status bar, so the bar's icons must be light whatever the phone's own
// theme is. Capacitor's SystemBarsStyle.Dark means light icons on a dark background. The navigation bar is left alone: the
// footer under it is the page surface.
describe('styleStatusBar', () => {
  it('sets the status bar to light icons once in the APK, and touches no other bar', async () => {
    native(true)
    await styleStatusBar()
    expect(SystemBars.setStyle).toHaveBeenCalledTimes(1)
    expect(SystemBars.setStyle).toHaveBeenCalledWith({ style: 'DARK', bar: 'StatusBar' })
  })

  it('does nothing on the web, where the plugin has no bars to style', async () => {
    native(false)
    await styleStatusBar()
    expect(SystemBars.setStyle).not.toHaveBeenCalled()
  })

  it('never breaks startup when the call is rejected', async () => {
    native(true)
    vi.mocked(SystemBars.setStyle).mockRejectedValueOnce(new Error('UNAVAILABLE'))
    await expect(styleStatusBar()).resolves.toBeUndefined()
    expect(SystemBars.setStyle).toHaveBeenCalledTimes(1)
  })

  it('never breaks startup when the call throws before it returns a promise', async () => {
    native(true)
    vi.mocked(SystemBars.setStyle).mockImplementationOnce(() => {
      throw new Error('not implemented')
    })
    await expect(styleStatusBar()).resolves.toBeUndefined()
  })
})

describe('main.tsx', () => {
  it('styles the status bar at startup, without waiting for it', () => {
    expect(mainSource).toMatch(/import \{ styleStatusBar \} from '\.\/systemBars'/)
    expect(mainSource).toMatch(/void styleStatusBar\(\)/)
  })
})
