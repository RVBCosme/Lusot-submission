import type { ReactNode } from 'react'
import { T } from '../i18n'
import { routeHash, type Route } from '../router'
import { BottomNav } from './BottomNav'
import { ErrorBoundary } from './ErrorBoundary'
import { OfflineBanner } from '../components/OfflineBanner'
import { LanguageSwitch } from './LanguageSwitch'
import { ScreenLine } from './ScreenLine'

// The shell fills the viewport and never scrolls; only the screen in <main> does. So the bar with the screen line
// and the nav stays in view on every screen without covering any of it. Its z-index sits above Leaflet's panes and
// controls (400 to 1,000), so a map can't draw over it. The padding is MS1's safe-area, clear of the phone's bars.
// Every colour and size comes from the tokens (styles/tokens.css) through Tailwind's theme.
export function Layout({ route, apiReady, children }: { route: Route; apiReady: boolean; children: ReactNode }) {
  return (
    <div className="safe-area flex h-screen flex-col supports-[height:100dvh]:h-dvh">
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-outline pb-2">
        <p className="text-title font-bold">Lusot</p>
        <LanguageSwitch />
      </header>
      {!apiReady && (
        <div role="alert" className="mt-2 rounded-control border border-outline p-2">
          <p>
            <T k="layout.noApi" />
          </p>
          <p className="text-small text-ink-2">
            <T k="layout.noApiDetail" />
          </p>
        </div>
      )}
      <OfflineBanner />
      {/* The key gives each route a fresh <main>, so a new screen starts at its top. The side padding, taken back by
          the negative margin, leaves room for a focus ring at the screen's edge, which a scrolling box would clip. It is
          a tab stop, so a keyboard can scroll a screen that has nothing else to focus, such as the privacy policy (axe's
          scrollable-region-focusable, WCAG 2.1.1). */}
      <main key={routeHash(route)} tabIndex={0} className="relative -mx-2 min-h-0 flex-1 overflow-y-auto px-2 py-4">
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
      <footer className="relative z-[1100] shrink-0 bg-surface">
        <ScreenLine />
        <BottomNav route={route} reportDisabled={!apiReady} />
      </footer>
    </div>
  )
}
