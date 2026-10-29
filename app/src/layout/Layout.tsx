import type { ReactNode } from 'react'
import { T } from '../i18n'
import { routeHash, type Route } from '../router'
import { BottomNav } from './BottomNav'
import { LanguageSwitch } from './LanguageSwitch'
import { ScreenLine } from './ScreenLine'

// The shell fills the viewport and never scrolls; only the screen in <main> does. So the bar with the screen line
// and the nav stays in view on every screen without covering any of it. Its z-index sits above Leaflet's panes and
// controls (400 to 1,000), so a map can't draw over it. The padding is MS1's safe-area, clear of the phone's bars.
export function Layout({ route, apiReady, children }: { route: Route; apiReady: boolean; children: ReactNode }) {
  return (
    <div className="safe-area flex h-screen flex-col supports-[height:100dvh]:h-dvh">
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-neutral-300 pb-2">
        <p className="text-xl font-bold">Lusot</p>
        <LanguageSwitch />
      </header>
      {!apiReady && (
        <div role="alert" className="mt-2 rounded border border-neutral-400 p-2">
          <p>
            <T k="layout.noApi" />
          </p>
          <p className="text-sm">
            <T k="layout.noApiDetail" />
          </p>
        </div>
      )}
      {/* The key gives each route a fresh <main>, so a new screen starts at its top. */}
      <main key={routeHash(route)} className="relative min-h-0 flex-1 overflow-y-auto py-4">
        {children}
      </main>
      <footer className="relative z-[1100] shrink-0 bg-white">
        <ScreenLine />
        <BottomNav route={route} reportDisabled={!apiReady} />
      </footer>
    </div>
  )
}
