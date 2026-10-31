import { useMemo, useSyncExternalStore } from 'react'

// The app's hash routes (C620), with #/licences for C636. Hash routes need no rewrite rule on any host, and work
// the same in the APK and offline.
export type Route =
  | { name: 'map' }
  | { name: 'report' }
  | { name: 'tested' }
  | { name: 'about' }
  | { name: 'privacy' }
  | { name: 'licences' }
  | { name: 'pin'; id: string }

const PAGES = ['map', 'report', 'tested', 'about', 'privacy', 'licences'] as const

// A pin's public id is its report id (MS4's C504). The app navigates only to pins it read from the API.
const PIN_ID = /^[A-Za-z0-9_-]{1,64}$/
const PIN_PREFIX = '#/pin/'

// Any hash the app doesn't know, an empty one included, reads as the map, the home screen.
export function parseHash(hash: string): Route {
  const page = PAGES.find((name) => hash === `#/${name}`)
  if (page !== undefined) return { name: page }
  if (hash.startsWith(PIN_PREFIX)) {
    const id = hash.slice(PIN_PREFIX.length)
    if (PIN_ID.test(id)) return { name: 'pin', id }
  }
  return { name: 'map' }
}

export function routeHash(route: Route): string {
  return route.name === 'pin' ? `${PIN_PREFIX}${route.id}` : `#/${route.name}`
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash)
  return useMemo(() => parseHash(hash), [hash])
}

// Adds a history entry, so the phone's back button returns to the screen before.
export function navigate(route: Route): void {
  window.location.hash = routeHash(route)
}
