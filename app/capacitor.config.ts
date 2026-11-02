import type { CapacitorConfig } from '@capacitor/cli'
// A JSON import with its attribute, never node:fs: the config test imports this file under tsconfig.app.json, which
// has no Node types, and Node loads it natively when `cap sync` reads the config.
import pkg from './package.json' with { type: 'json' }

const config: CapacitorConfig = {
  appId: 'io.github.rvbcosme.lusot',
  appName: 'Lusot',
  webDir: 'dist',
  // The WebView's user agent ends with "Lusot/<version>", the version in package.json, so the app names itself in
  // its requests.
  appendUserAgent: 'Lusot/' + pkg.version,
  // The default ('debug') logs every plugin result in debug builds, GPS fixes included, and
  // CLAUDE.md never logs exact locations. Debug the WebView with DevTools instead.
  loggingBehavior: 'none',
  // The WebView's own background, the brand navy (--lusot-brand-navy in src/styles/tokens.css), so no white shows
  // between the navy splash and the page's navy loading screen.
  backgroundColor: '#041A3A',
  plugins: {
    // The page sets viewport-fit=cover (index.html), and the plugin reads it only once the page is loaded. Saying it
    // here keeps the first layout from jumping when it does.
    SystemBars: { initialViewportFitValueHint: 'cover' },
  },
}

export default config
