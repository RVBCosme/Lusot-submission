import { vi } from 'vitest'

// Whether the page asks for reduced motion (setup.ts's stub says no). A test that checks a drawing's final frame asks
// for it, so the overlay shows whole at once (C615); the overlay's timing tests ask for motion and step the clock.
const realMatchMedia = window.matchMedia
export function prefersReducedMotion(reduce: boolean): void {
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
    ...realMatchMedia(query),
    matches: reduce && query === '(prefers-reduced-motion: reduce)',
  }))
}
