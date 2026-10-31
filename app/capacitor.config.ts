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
}

export default config
