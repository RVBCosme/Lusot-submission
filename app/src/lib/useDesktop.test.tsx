import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DESKTOP_QUERY, useDesktop } from './useDesktop'

// A window whose desktop query can be flipped by the test, as a browser does when its window is resized across lg.
function window_(matches: boolean) {
  const listeners = new Set<() => void>()
  const state = { matches }
  const ask = vi.spyOn(window, 'matchMedia').mockImplementation(
    (query) =>
      ({
        get matches() {
          return state.matches
        },
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  )
  return {
    ask,
    listeners,
    resize(to: boolean) {
      state.matches = to
      act(() => listeners.forEach((listener) => listener()))
    },
  }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('useDesktop', () => {
  it("asks for Tailwind's lg breakpoint, 64 rem, so the script and the stylesheet agree", () => {
    const win = window_(false)
    renderHook(() => useDesktop())

    expect(DESKTOP_QUERY).toBe('(min-width: 64rem)')
    expect(win.ask).toHaveBeenCalledWith(DESKTOP_QUERY)
  })

  it('is false below lg and follows the window across it, both ways', () => {
    const win = window_(false)
    const { result } = renderHook(() => useDesktop())
    expect(result.current).toBe(false)

    win.resize(true)
    expect(result.current).toBe(true)

    win.resize(false)
    expect(result.current).toBe(false)
  })

  it('is true when the window opens at lg or wider', () => {
    window_(true)
    expect(renderHook(() => useDesktop()).result.current).toBe(true)
  })

  it('stops listening when the screen goes', () => {
    const win = window_(false)
    const { unmount } = renderHook(() => useDesktop())
    expect(win.listeners.size).toBe(1)

    unmount()

    expect(win.listeners.size).toBe(0)
  })

  it('is false where the browser has no matchMedia', () => {
    const original = window.matchMedia
    // @ts-expect-error a browser without matchMedia
    window.matchMedia = undefined
    try {
      expect(renderHook(() => useDesktop()).result.current).toBe(false)
    } finally {
      window.matchMedia = original
    }
  })
})
