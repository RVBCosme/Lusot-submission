// The installable web app (C621, MS5 Task 16), through vite-plugin-pwa 2. The service worker precaches the app's own
// files only: its scripts, styles, page, fonts, icons, the manifest and the licences. Nothing is cached at run time,
// so API calls, photo links and OpenStreetMap's tiles always go to the network (its tile policy; a cached report would
// be a stale one). It updates by itself (autoUpdate: a new deploy's worker takes over at once), and the app, which
// registers it by hand on the web only (src/pwa.ts), reloads into the new version as soon as the report flow holds no
// photo or report id. deploy:web puts sw.js up last, once the new pages are live (scripts/deploy_web.mjs). The
// manifest is the static public/manifest.webmanifest.
import type { VitePWAOptions } from 'vite-plugin-pwa'

export const pwaOptions: Partial<VitePWAOptions> = {
  registerType: 'autoUpdate',
  injectRegister: null,
  manifest: false,
  workbox: {
    globPatterns: ['**/*.{js,css,html,woff2,svg,png,txt,webmanifest}'],
    // The licences page's text is about 400 KB, over Workbox's 2 MiB default only if it grows fivefold.
    maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
    cleanupOutdatedCaches: true,
    navigateFallback: 'index.html',
  },
}
