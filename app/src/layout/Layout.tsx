import type { ReactNode } from 'react'
import { T } from '../i18n'
import { routeHash, type Route } from '../router'
import { BottomNav } from './BottomNav'
import { BrandMark } from './BrandMark'
import { ErrorBoundary } from './ErrorBoundary'
import { OfflineBanner } from '../components/OfflineBanner'
import { LanguageSwitch } from './LanguageSwitch'
import { ScreenLine } from './ScreenLine'

// The shell fills the viewport and never scrolls; only the screen in <main> does. So the bar with the screen line and the
// nav stays in view on every screen without covering any of it. Its z-index sits above Leaflet's panes and controls (400
// to 1,000), so a map can't draw over it. The padding is MS1's safe-area, clear of the phone's bars. Every colour and size
// comes from the tokens (styles/tokens.css) through Tailwind's theme.
//
// From lg (64 rem) the shell is a grid of four rows and one column, the column free to shrink below its content: the top
// bar, the notices, the screen, and the screen line, each across the whole width (`col-span-full`). The nav is
// drawn twice, and each width shows one copy (the other is `display: none`, so it is out of the tab order and the
// accessibility tree): the phone's bar of tabs in the footer, after the screen, and from lg a copy in the header, between
// the brand and the language switch, so the keyboard and the screen reader meet the bar in the order the eye does (WCAG
// 2.4.3, 1.3.2). The footer gives its children to the grid (`contents`). The header is a row of its own across the grid, a
// flex row, so it can be one box: the brand navy (`app-bar`, index.css) runs out through the shell's padding to the window's
// edges and under the system bars, at both widths. The screens are centred at 72 rem, by the screen's own side padding,
// since a wrapper would break the screens that fill it (`min-h-full`); the map runs to the edges of the window. Below lg none
// of this applies.
export function Layout({ route, apiReady, children }: { route: Route; apiReady: boolean; children: ReactNode }) {
  const mapScreen = route.name === 'map'
  return (
    <div className="safe-area flex h-screen flex-col supports-[height:100dvh]:h-dvh lg:grid lg:grid-cols-[minmax(0,1fr)] lg:grid-rows-[auto_auto_minmax(0,1fr)_auto]">
      <header className="app-bar flex flex-wrap items-center justify-between gap-x-3 gap-y-1 pb-2 lg:col-span-full lg:row-start-1 lg:flex-nowrap lg:justify-start lg:px-4 lg:pb-0">
        <div className="flex items-center gap-2">
          <BrandMark className="h-8 w-auto shrink-0" />
          <p className="text-title font-bold text-brand-pale">Lusot</p>
        </div>
        <BottomNav
          route={route}
          reportDisabled={!apiReady}
          onBrand
          className="hidden lg:relative lg:z-[1100] lg:block lg:flex-1 lg:py-2"
        />
        <LanguageSwitch onBrand />
      </header>
      {/* The notices share one row of the grid, one above the other. Empty, they take no room. */}
      <div className="lg:col-span-full lg:row-start-2 lg:px-4">
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
      </div>
      {/* The key gives each route a fresh <main>, so a new screen starts at its top. The side padding, taken back by
          the negative margin, leaves room for a focus ring at the screen's edge, which a scrolling box would clip. It is
          a tab stop, so a keyboard can scroll a screen that has nothing else to focus, such as the privacy policy (axe's
          scrollable-region-focusable, WCAG 2.1.1). From lg the screen reaches the window's edges and has no such room, so
          its ring is drawn inside its box. */}
      <main
        key={routeHash(route)}
        tabIndex={0}
        className={`relative -mx-2 min-h-0 flex-1 overflow-y-auto px-2 py-4 lg:col-span-full lg:row-start-3 lg:mx-0 lg:focus-visible:-outline-offset-3 ${
          mapScreen ? 'lg:p-0' : 'lg:page-x lg:py-6'
        }`}
      >
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
      <footer className="relative z-[1100] shrink-0 bg-surface lg:contents">
        <ScreenLine />
        <BottomNav route={route} reportDisabled={!apiReady} className="lg:hidden" />
      </footer>
    </div>
  )
}
