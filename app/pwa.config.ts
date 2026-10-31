// The installable web app (C621, MS5 Task 16), through vite-plugin-pwa 2. The service worker precaches the app's own
// files only: its scripts, styles, page, fonts, icons, the manifest and the licences. Nothing is cached at run time,
// so API calls, photo links and OpenStreetMap's tiles always go to the network (its tile policy; a cached report would
// be a stale one). The worker is registered by hand, on the web only (src/pwa.ts), as "prompt": a new deploy's worker
// waits only while the report flow holds a photo or a report id, then takes over and the page reloads, and the app
// asks for a new deploy each time it comes to the front, so it never stays behind a cached old version. The manifest
// is the static public/manifest.webmanifest.
import type { VitePWAOptions } from 'vite-plugin-pwa'

export const pwaOptions: Partial<VitePWAOptions> = {
  registerType: 'prompt',
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
