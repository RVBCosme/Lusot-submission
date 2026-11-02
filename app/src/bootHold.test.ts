import { Capacitor } from '@capacitor/core'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import indexHtml from '../index.html?raw'
import { renderAfterBoot } from './bootHold'
import mainSource from './main.tsx?raw'

// The APK holds the loading screen for 5 seconds on a cold start, its bar filling 20 % a second in five steps, and then
// renders the app (Rene, Nov 2). The website renders at once. The module is mocked down to the one call the file makes;
// the rest of Capacitor stays its own.
vi.mock('@capacitor/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@capacitor/core')>()
  return { ...actual, Capacitor: { ...actual.Capacitor, isNativePlatform: vi.fn(() => false) } }
})

const native = (on: boolean) => vi.mocked(Capacitor.isNativePlatform).mockReturnValue(on)

// index.html's own markup inside #root, so the selectors the hold uses are checked against the real screen.
const rootMarkup = new DOMParser().parseFromString(indexHtml, 'text/html').getElementById('root')!.innerHTML

function mount(): { boot: HTMLElement; bar: HTMLElement } {
  document.body.innerHTML = ''
  const container = document.createElement('div')
  container.id = 'root'
  container.innerHTML = rootMarkup
  document.body.append(container)
  return { boot: container.querySelector<HTMLElement>('#boot')!, bar: container.querySelector<HTMLElement>('[role="progressbar"]')! }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  native(false)
  document.body.innerHTML = ''
})

describe('in the APK', () => {
  it('holds the render for 5 seconds, and renders right after the fifth step', () => {
    native(true)
    mount()
    const render = vi.fn()
    renderAfterBoot(render)
    expect(render).not.toHaveBeenCalled()
    vi.advanceTimersByTime(4999)
    expect(render).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(render).toHaveBeenCalledTimes(1)
    // It renders once, and the clock has nothing left to run.
    vi.advanceTimersByTime(20_000)
    expect(render).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('fills the bar 20 % a second: 20 at once, then 40, 60, 80, 100 at 1 to 4 seconds, announced on the progress bar', () => {
    native(true)
    const { boot, bar } = mount()
    const render = vi.fn()
    renderAfterBoot(render)
    // At the start it is a determinate bar at its first step, not the indeterminate one.
    expect(bar.getAttribute('aria-valuemin')).toBe('0')
    expect(bar.getAttribute('aria-valuemax')).toBe('100')
    expect(bar.getAttribute('aria-valuenow')).toBe('20')
    expect(boot.classList.contains('boot-steps')).toBe(true)
    expect(bar.style.getPropertyValue('--boot-progress')).toBe('20%')
    // The first step shows at once, from the sliding bar: the easing between steps (boot-eased) is not on yet.
    expect(boot.classList.contains('boot-eased')).toBe(false)

    for (const percent of [40, 60, 80, 100]) {
      vi.advanceTimersByTime(999)
      // Still the step before, until the second is over.
      expect(bar.getAttribute('aria-valuenow'), `just before ${percent}`).toBe(String(percent - 20))
      expect(boot.classList.contains('boot-eased'), `easing just before ${percent}`).toBe(percent > 40)
      vi.advanceTimersByTime(1)
      expect(bar.getAttribute('aria-valuenow'), `at ${percent}`).toBe(String(percent))
      expect(bar.style.getPropertyValue('--boot-progress'), `fill at ${percent}`).toBe(`${percent}%`)
      // From the second step on, each step eases.
      expect(boot.classList.contains('boot-eased'), `easing at ${percent}`).toBe(true)
    }
    // The full bar is seen for a second: 100 from 4 s, and the render comes only at 5 s.
    expect(render).not.toHaveBeenCalled()
    vi.advanceTimersByTime(999)
    expect(bar.getAttribute('aria-valuenow')).toBe('100')
    expect(render).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(render).toHaveBeenCalledTimes(1)
    expect(bar.getAttribute('aria-valuenow')).toBe('100')
  })

  it('keeps the bar\'s name, taken from the status text, and the rest of the screen as it was', () => {
    native(true)
    const { boot, bar } = mount()
    renderAfterBoot(vi.fn())
    vi.advanceTimersByTime(2500)
    const name = document.getElementById(bar.getAttribute('aria-labelledby') ?? '')
    expect(name?.textContent).toBe('Loading Lusot…')
    expect(boot.getAttribute('aria-busy')).toBe('true')
    expect(bar.hasAttribute('aria-valuetext')).toBe(false)
  })

  it('renders at once when the platform check throws', () => {
    vi.mocked(Capacitor.isNativePlatform).mockImplementation(() => {
      throw new Error('not implemented')
    })
    const { bar } = mount()
    const render = vi.fn()
    renderAfterBoot(render)
    expect(render).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
    expect(bar.hasAttribute('aria-valuenow')).toBe(false)
  })

  it('renders at once when the loading screen is not in the page', () => {
    native(true)
    document.body.innerHTML = '<div id="root"></div>'
    const render = vi.fn()
    renderAfterBoot(render)
    expect(render).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('renders at once, and once, when a step throws, and the clock stops', () => {
    native(true)
    const { bar } = mount()
    const setAttribute = bar.setAttribute.bind(bar)
    vi.spyOn(bar, 'setAttribute').mockImplementation((name, value) => {
      if (name === 'aria-valuenow' && value === '60') throw new Error('gone')
      setAttribute(name, value)
    })
    const render = vi.fn()
    renderAfterBoot(render)
    vi.advanceTimersByTime(1000)
    expect(bar.getAttribute('aria-valuenow')).toBe('40')
    expect(render).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1000)
    expect(render).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
    vi.advanceTimersByTime(20_000)
    expect(render).toHaveBeenCalledTimes(1)
  })

  it('renders at once when the first mark of the hold throws', () => {
    native(true)
    const { bar } = mount()
    vi.spyOn(bar, 'setAttribute').mockImplementation(() => {
      throw new Error('gone')
    })
    const render = vi.fn()
    renderAfterBoot(render)
    expect(render).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('on the web', () => {
  it('renders at once, and leaves the bar indeterminate', () => {
    native(false)
    const { boot, bar } = mount()
    const render = vi.fn()
    renderAfterBoot(render)
    expect(render).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
    for (const attribute of ['aria-valuenow', 'aria-valuemin', 'aria-valuemax', 'aria-valuetext']) {
      expect(bar.hasAttribute(attribute), attribute).toBe(false)
    }
    expect(boot.classList.contains('boot-steps')).toBe(false)
    expect(boot.classList.contains('boot-eased')).toBe(false)
    expect(bar.style.getPropertyValue('--boot-progress')).toBe('')
  })
})

describe('main.tsx', () => {
  it('renders through the hold, on a root made at once', () => {
    expect(mainSource).toMatch(/import \{ renderAfterBoot \} from '\.\/bootHold'/)
    expect(mainSource).toMatch(/const root = createRoot\(document\.getElementById\('root'\)!, rootErrorOptions\)/)
    expect(mainSource).toMatch(/renderAfterBoot\(\(\) =>\s*root\.render\(/)
    // The only render is the one the hold calls.
    expect(mainSource.match(/\.render\(/g)).toHaveLength(1)
  })
})
