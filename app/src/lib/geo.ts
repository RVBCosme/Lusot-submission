// The GPS fix and the pin's limits (C603). A report says "at this spot", so the person's position must be good, 50 m
// or better, and the pin they place may move only a little, at most 100 m from it. A position is private (CLAUDE.md):
// nothing here logs it, shows it as numbers or keeps it, and an error carries only a code or an accuracy.
import { Capacitor } from '@capacitor/core'
import { Geolocation, type PositionOptions, type WatchPositionCallback } from '@capacitor/geolocation'
import type { StringKey } from '../i18n/en'

export type LatLng = { lat: number; lng: number }
export type Fix = LatLng & { accuracyM: number }

// The window for a good fix, counted from the first position update, never from a permission prompt.
export const FIX_WINDOW_MS = 20_000
// The accuracy a fix must have, in metres, and how far the pin may move from it.
export const GOOD_FIX_M = 50
export const MAX_NUDGE_M = 100

const EARTH_RADIUS_M = 6_371_008.8
const RAD = Math.PI / 180

// The great-circle distance in metres between two points (the haversine formula).
export function distanceM(a: LatLng, b: LatLng): number {
  const dLat = (b.lat - a.lat) * RAD
  const dLng = (b.lng - a.lng) * RAD
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * RAD) * Math.cos(b.lat * RAD) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)))
}

// `target` itself when it is within `maxM` of `origin`; otherwise the point `maxM` from `origin` on the same bearing.
export function clampToRadius(origin: LatLng, target: LatLng, maxM: number = MAX_NUDGE_M): LatLng {
  if (distanceM(origin, target) <= maxM) return target
  const lat1 = origin.lat * RAD
  const lng1 = origin.lng * RAD
  const lat2 = target.lat * RAD
  const dLng = (target.lng - origin.lng) * RAD
  const bearing = Math.atan2(
    Math.sin(dLng) * Math.cos(lat2),
    Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng),
  )
  const angle = maxM / EARTH_RADIUS_M
  const lat = Math.asin(Math.sin(lat1) * Math.cos(angle) + Math.cos(lat1) * Math.sin(angle) * Math.cos(bearing))
  const lng =
    lng1 +
    Math.atan2(
      Math.sin(bearing) * Math.sin(angle) * Math.cos(lat1),
      Math.cos(angle) - Math.sin(lat1) * Math.sin(lat),
    )
  return { lat: lat / RAD, lng: ((((lng / RAD + 180) % 360) + 360) % 360) - 180 }
}

// The point this many metres north and east of `from`, by flat-earth arithmetic: good to millimetres over the
// pin's 100 m, which is all it is used for (the arrow keys' steps).
export function moveM(from: LatLng, northM: number, eastM: number): LatLng {
  return {
    lat: from.lat + northM / EARTH_RADIUS_M / RAD,
    lng: from.lng + eastM / (EARTH_RADIUS_M * Math.cos(from.lat * RAD)) / RAD,
  }
}

// How far the person moved the pin, in whole metres, never over 100. It is the only thing about the pin the app sends
// besides the position itself (`nudgeM`, C603).
export function nudgeM(origin: LatLng, placed: LatLng): number {
  return Math.min(MAX_NUDGE_M, Math.round(distanceM(origin, placed)))
}

// No fix of 50 m or better came in the window, or none came at all (`bestAccuracyM` is then undefined): the watch's
// own timeout on a cold GPS lands here too.
export class PoorFix extends Error {
  readonly bestAccuracyM: number | undefined

  constructor(bestAccuracyM?: number) {
    super('poor_fix')
    this.name = 'PoorFix'
    this.bestAccuracyM = bestAccuracyM
  }
}

// The location could not be used for a reason other than accuracy. `code` is the plugin's own error code
// (OS-PLUG-GLOC-nnnn), the browser's code by its standard name, or 'unknown'; never the error's text, which can
// carry more than a code.
export class LocationDenied extends Error {
  readonly code: string

  constructor(code: string) {
    super('location_denied')
    this.name = 'LocationDenied'
    this.code = code
  }
}

// The two things waitForFix needs of the plugin, so a test can give it a fake.
export type GeoWatch = {
  watchPosition(options: PositionOptions, callback: WatchPositionCallback): Promise<string>
  clearWatch(options: { id: string }): Promise<void>
}

const PLUGIN_TIMEOUT = 'OS-PLUG-GLOC-0010'

// A watch error's code as a string. The browser's numbers 1, 2 and 3 get their standard names.
function errorCode(err: unknown): string {
  const code = typeof err === 'object' && err !== null && 'code' in err ? err.code : undefined
  if (code === 1) return 'PERMISSION_DENIED'
  if (code === 2) return 'POSITION_UNAVAILABLE'
  if (code === 3) return 'TIMEOUT'
  return typeof code === 'string' ? code : 'unknown'
}

const isTimeout = (code: string) => code === 'TIMEOUT' || code === PLUGIN_TIMEOUT

// The plugin's own code for "permission refused", apart from the browser's 'PERMISSION_DENIED' above. Android
// resolves the permission request with 'denied' rather than throwing, so waitForFix raises this code itself.
const NATIVE_DENIED = 'OS-PLUG-GLOC-0003'

// A refusal, in either of its two spellings. Once a position has come, it is the only error that ends the wait early.
const isRefusal = (code: string) => code === 'PERMISSION_DENIED' || code === NATIVE_DENIED

// Rejects with the signal's reason when it aborts, whatever `promise` does after.
function orAbort<T>(promise: Promise<T>, signal: AbortSignal | undefined): Promise<T> {
  if (signal === undefined) return promise
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(signal.reason)
    signal.addEventListener('abort', onAbort, { once: true })
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort))
  })
}

// On Android the plugin asks for location permission itself, once, here. It answers 'denied' for a refusal and
// throws when the phone's location services are off. Someone who allows only approximate location (Android 12 and
// later) passes this and then never reaches 50 m, which the poor-fix line explains.
async function askNativePermission(signal: AbortSignal | undefined): Promise<void> {
  let status: Awaited<ReturnType<typeof Geolocation.requestPermissions>>
  try {
    status = await orAbort(Geolocation.requestPermissions(), signal)
  } catch (err) {
    if (signal?.aborted) throw signal.reason
    throw new LocationDenied(errorCode(err))
  }
  if (status.location === 'denied' && status.coarseLocation === 'denied') throw new LocationDenied(NATIVE_DENIED)
}

export type WaitForFixOptions = {
  maxWaitMs?: number
  goodM?: number
  watch?: GeoWatch
  signal?: AbortSignal
}

// Watches the position until one update is 50 m or better, and resolves with it. The watch starts now, so the caller
// starts this once the camera stream is open (C603), after the camera's own prompt. The APK first asks for
// permission. The window of `maxWaitMs` (20,000 ms) counts from the first position update, never from the prompt or
// from the start, so a slow prompt or a slow first fix never uses it up; the watch's own timeout, the same length,
// ends a wait for a first position. It rejects with PoorFix when the window passes with no good fix, or when the watch
// times out before any position; with LocationDenied for any other error before a position; and, after one, only for
// a refused permission (the window decides the rest). The watch is cleared however it ends, including on an abort.
export async function waitForFix({
  maxWaitMs = FIX_WINDOW_MS,
  goodM = GOOD_FIX_M,
  watch = Geolocation,
  signal,
}: WaitForFixOptions = {}): Promise<Fix> {
  signal?.throwIfAborted()
  if (Capacitor.isNativePlatform()) await askNativePermission(signal)
  signal?.throwIfAborted()

  // The defaults wait 5 s or more between Android's updates; 1 s gets the window several to choose from.
  const options: PositionOptions = { enableHighAccuracy: true, timeout: maxWaitMs }
  if (Capacitor.getPlatform() === 'android') {
    options.interval = 1_000
    options.minimumUpdateInterval = 1_000
  }

  return new Promise<Fix>((resolve, reject) => {
    let watchId: string | undefined
    let finished = false
    let windowTimer: ReturnType<typeof setTimeout> | undefined
    let seen = false
    let best: number | undefined

    const stopWatch = (id: string) => {
      try {
        Promise.resolve(watch.clearWatch({ id })).catch(() => {})
      } catch {
        // A watch that can't be cleared is already gone; there is nothing to report.
      }
    }
    const finish = (settle: () => void) => {
      if (finished) return
      finished = true
      clearTimeout(windowTimer)
      signal?.removeEventListener('abort', onAbort)
      if (watchId !== undefined) stopWatch(watchId)
      settle()
    }
    const onAbort = () => finish(() => reject(signal?.reason))
    signal?.addEventListener('abort', onAbort, { once: true })

    const onUpdate: WatchPositionCallback = (position, err) => {
      if (finished) return
      if (position === null || position === undefined) {
        const code = errorCode(err)
        // Before any position, a timeout is a PoorFix and any other error ends the wait. After one, the window is
        // already bounded at 20 s: a timeout or a passing error (Chrome and Android raise POSITION_UNAVAILABLE and
        // OS-PLUG-GLOC-0002 now and then mid-watch) must not throw away a good fix that may still come, so only a
        // refused permission ends the wait early, and the window decides the rest.
        if (seen) {
          if (isRefusal(code)) finish(() => reject(new LocationDenied(code)))
          return
        }
        finish(() => reject(isTimeout(code) ? new PoorFix() : new LocationDenied(code)))
        return
      }
      const { latitude: lat, longitude: lng, accuracy: accuracyM } = position.coords
      if (!Number.isFinite(lat) || !Number.isFinite(lng) || !Number.isFinite(accuracyM)) return
      if (accuracyM <= goodM) {
        finish(() => resolve({ lat, lng, accuracyM }))
        return
      }
      best = best === undefined ? accuracyM : Math.min(best, accuracyM)
      if (!seen) {
        seen = true
        windowTimer = setTimeout(() => finish(() => reject(new PoorFix(best))), maxWaitMs)
      }
    }

    const fail = (err: unknown) => finish(() => reject(new LocationDenied(errorCode(err))))
    try {
      watch.watchPosition(options, onUpdate).then((id) => {
        // The watch may have ended before its id arrived, by a good fix or an abort.
        if (finished) stopWatch(id)
        else watchId = id
      }, fail)
    } catch (err) {
      fail(err)
    }
  })
}

// Which line says why the location couldn't be used (the strings are in i18n/en.ts). The plugin's codes, from its
// error table: 0003 permission refused, 0007 location services off, 0009 the request to turn them on refused, 0010
// timed out (which waitForFix reports as PoorFix, so it shares that line), 0017 location and network both off.
const LINE_BY_CODE = new Map<string, StringKey>([
  [NATIVE_DENIED, 'location.denied'],
  ['PERMISSION_DENIED', 'location.denied'],
  ['OS-PLUG-GLOC-0007', 'location.servicesOff'],
  ['OS-PLUG-GLOC-0009', 'location.enableDenied'],
  [PLUGIN_TIMEOUT, 'location.poor'],
  ['OS-PLUG-GLOC-0017', 'location.allOff'],
])

export function locationLine(err: unknown): StringKey {
  if (err instanceof PoorFix) return 'location.poor'
  if (err instanceof LocationDenied) return LINE_BY_CODE.get(err.code) ?? 'location.unavailable'
  return 'location.unavailable'
}
