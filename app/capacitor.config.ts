import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'io.github.rvbcosme.lusot',
  appName: 'Lusot',
  webDir: 'dist',
  // The default ('debug') logs every plugin result in debug builds, GPS fixes included, and
  // CLAUDE.md never logs exact locations. Debug the WebView with DevTools instead.
  loggingBehavior: 'none',
}

export default config
