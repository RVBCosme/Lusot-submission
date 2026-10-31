import { describe, expect, it } from 'vitest'
import { pwaOptions } from './pwa.config.ts'

// The service worker precaches the app's own files only (C621): no runtime caching, so API calls, photo links and
// map tiles always go to the network; and it updates by itself, the app choosing when to reload (src/pwa.ts).
describe('the PWA options', () => {
  it('precache the app\'s own files, fonts, icons and licences, at the site\'s root and below, and cache nothing at run time', () => {
    expect(pwaOptions.workbox?.runtimeCaching).toBeUndefined()
    expect(pwaOptions.workbox?.globPatterns).toEqual(['**/*.{js,css,html,woff2,svg,png,txt,webmanifest}'])
    expect(pwaOptions.workbox?.cleanupOutdatedCaches).toBe(true)
  })

  it('update by themselves, as C621 and the plan say, registered by hand, with the static manifest', () => {
    expect(pwaOptions.registerType).toBe('autoUpdate')
    expect(pwaOptions.injectRegister).toBeNull()
    expect(pwaOptions.manifest).toBe(false)
  })
})
