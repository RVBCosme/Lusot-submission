// The service worker's registration (C621, MS5 Task 16): on the web only, never in the APK. A new deploy's worker is
// taken at once, with a reload, unless the report flow holds a photo or a report id (Review Focus 4): then it waits,
// and is taken as soon as the flow lets go. The app looks for a new deploy when it comes back to the front and every
// hour while it is open, so an open tab never stays on an old version.
import { Capacitor } from '@capacitor/core'

// vite-plugin-pwa's registerSW, as this file uses it.
export type Register = (options: {
  immediate?: boolean
  onNeedRefresh?(): void
  onRegisteredSW?(swUrl: string, registration: ServiceWorkerRegistration | undefined): void
}) => (reloadPage?: boolean) => Promise<void>

const HOLD_RETRY_MS = 5000
const CHECK_EVERY_MS = 60 * 60_000

type Deps = { native: boolean; register(): Promise<Register> }

const defaults = (): Deps => ({
  native: Capacitor.isNativePlatform(),
  register: async () => (await import('virtual:pwa-register')).registerSW as Register,
})

export async function registerServiceWorker(isBusy: () => boolean, deps: Deps = defaults()): Promise<void> {
  if (deps.native) return
  const registerSW = await deps.register()
  let registration: ServiceWorkerRegistration | undefined
  let taking = false
  // Takes the new worker and reloads, once nothing is held.
  const take = () => {
    if (isBusy()) {
      setTimeout(take, HOLD_RETRY_MS)
      return
    }
    void updateSW(true)
  }
  const updateSW = registerSW({
    immediate: true,
    onNeedRefresh() {
      if (taking) return
      taking = true
      take()
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
