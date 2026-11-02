import { useSyncExternalStore } from 'react'

// Tailwind's `lg` breakpoint, 64 rem (1,024 px at the browser's own text size). Both are in rem, so the script and the
// stylesheet change together, even when the person has set a larger text size.
export const DESKTOP_QUERY = '(min-width: 64rem)'

function subscribe(onChange: () => void): () => void {
  if (typeof window.matchMedia !== 'function') return () => {}
  const query = window.matchMedia(DESKTOP_QUERY)
  query.addEventListener('change', onChange)
  return () => query.removeEventListener('change', onChange)
}

function read(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia(DESKTOP_QUERY).matches
}

// Whether the window is at `lg` or wider. Only for what a class can't do: the live map's `hidden` attribute below lg
// beats any utility, so the screen asks to keep the map beside its list. Everything else in the desktop layout is a class.
export function useDesktop(): boolean {
  return useSyncExternalStore(subscribe, read, () => false)
}
