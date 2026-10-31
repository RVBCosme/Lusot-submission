// The service worker's registration (C621, MS5 Task 16): on the web only, never in the APK. In vite-plugin-pwa's
// autoUpdate mode a new deploy's worker takes over by itself; the plugin then calls onNeedReload, which would
// otherwise reload the page at once. Here the reload waits while the report flow holds a photo or a report id (Review
// Focus 4), and comes as soon as the flow lets go. The app also looks for a new deploy whenever it comes back to the
// front and every hour while it is open, so a page the worker controls doesn't stay on an old version.
import { Capacitor } from '@capacitor/core'

// vite-plugin-pwa's registerSW, as this file uses it.
export type Register = (options: {
  immediate?: boolean
  onNeedReload?(): void
  onRegisteredSW?(swUrl: string, registration: ServiceWorkerRegistration | undefined): void
}) => unknown

const HOLD_RETRY_MS = 5000
const CHECK_EVERY_MS = 60 * 60_000

type Deps = { native: boolean; register(): Promise<Register>; reload(): void }

const defaults = (): Deps => ({
  native: Capacitor.isNativePlatform(),
  register: async () => (await import('virtual:pwa-register')).registerSW as Register,
  reload: () => window.location.reload(),
})

export async function registerServiceWorker(isBusy: () => boolean, deps: Deps = defaults()): Promise<void> {
  if (deps.native) return
  const registerSW = await deps.register()
  let registration: ServiceWorkerRegistration | undefined
  let reloading = false
  // Reloads into the new version, once nothing is held.
  const reloadWhenFree = () => {
    if (isBusy()) {
      setTimeout(reloadWhenFree, HOLD_RETRY_MS)
      return
    }
    deps.reload()
  }
  registerSW({
    immediate: true,
    onNeedReload() {
      if (reloading) return
      reloading = true
      reloadWhenFree()
    },
    onRegisteredSW(_url, found) {
      registration = found
    },
  })
  const look = () => {
    if (document.visibilityState !== 'visible') return
    registration?.update().catch(() => {
      // Offline, or the server is down: the next look tries again.
    })
  }
  document.addEventListener('visibilitychange', look)
  setInterval(look, CHECK_EVERY_MS)
}
