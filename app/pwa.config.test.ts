import { describe, expect, it } from 'vitest'
import { pwaOptions } from './pwa.config.ts'

// The service worker precaches the app's own files only (C621): no runtime caching, so API calls, photo links and
// map tiles always go to the network, and a new deploy's worker takes over as soon as the app lets it.
describe('the PWA options', () => {
  it('precache the app\'s own files, fonts, icons and licences, and cache nothing at run time', () => {
    expect(pwaOptions.workbox?.runtimeCaching).toBeUndefined()
    for (const ext of ['js', 'css', 'html', 'woff2', 'svg', 'png', 'txt']) {
      expect(pwaOptions.workbox?.globPatterns?.[0]).toContain(ext)
    }
    expect(pwaOptions.workbox?.cleanupOutdatedCaches).toBe(true)
  })

  it('register by hand, and keep the static manifest (public/manifest.webmanifest)', () => {
    expect(pwaOptions.injectRegister).toBeNull()
    expect(pwaOptions.manifest).toBe(false)
    // "prompt": a new worker waits until the app says so (src/pwa.ts), never mid-report; the app then reloads at once.
    expect(pwaOptions.registerType).toBe('prompt')
  })
})
