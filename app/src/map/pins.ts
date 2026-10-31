// The map's pin rules (C612, C613; plan "Map"): how strong a pin is drawn, how the person's own pin gives way to the API's
// copy, the list's order, how many other reports lie nearby, and the flag count that never goes down. Pure functions,
// except the session's two small memories, which live in this module and nowhere else: never in storage.
import type { Pin } from '../lib/api'
import { distanceM } from '../lib/geo'
import type { OwnPin } from '../report/flow'

const HOUR_MS = 3_600_000
// A live pin is full strength for its first hour, faded from 1 hour, and gone from 3 hours (plan §9).
const FADED_FROM_MS = HOUR_MS
const GONE_AT_MS = 3 * HOUR_MS
// "Nearby" is within 300 m and 3 hours (C613). MS4 rounds public positions to about 11 m (C514), so the own pin and
// its API copy can differ by that much: 15 m is the line between "the same pin" and "another".
const NEARBY_M = 300
const SAME_PIN_M = 15

export type Strength = 'full' | 'faded' | 'gone'

// A demo pin is ours, a credited photo from some other day, so it never fades. A live pin that doesn't read as a time
// can't be placed in the 3 hours, so it counts as gone rather than as fresh.
export function pinStrength(pin: Pin, now: Date): Strength {
  if (pin.mode === 'demo') return 'full'
  const age = now.getTime() - Date.parse(pin.capturedAt)
  if (age < FADED_FROM_MS) return 'full'
  return age < GONE_AT_MS ? 'faded' : 'gone'
}

// An id that `GET /map/pins` held. The pin screen asks for a report only with one of these (Task 2's review, S5-R5), so
// the route's own text, which anyone can type, never reaches `GET /reports/{id}`.
declare const pinIdBrand: unique symbol
export type PinId = string & { readonly [pinIdBrand]: true }

export function readPinId(pins: readonly Pin[], id: string): PinId | undefined {
  return pins.some((pin) => pin.id === id) ? (id as PinId) : undefined
}

export function isOwn(pin: Pin): pin is OwnPin {
  return (pin as Partial<OwnPin>).own === true
}

// The API stores the photo's time in seconds and the app sends milliseconds, so two copies of one report share the
// whole second. An unreadable time is NaN, which equals nothing.
const wholeSecond = (time: string) => Math.floor(Date.parse(time) / 1000)

// The pins with the person's own one added, unless the API already holds it: by its id, or else a pin taken in the same
// whole second within 15 m (C514's rounding). The list it is given is left as it was.
export function mergeOwnPin(pins: readonly Pin[], own?: OwnPin): Pin[] {
  if (own === undefined) return [...pins]
  const held = pins.some(
    (pin) =>
      pin.id === own.id ||
      (wholeSecond(pin.capturedAt) === wholeSecond(own.capturedAt) && distanceM(pin, own) <= SAME_PIN_M),
  )
  return held ? [...pins] : [...pins, own]
}

// A time that doesn't read as one sorts last.
const takenAt = (pin: Pin) => {
  const time = Date.parse(pin.capturedAt)
  return Number.isFinite(time) ? time : Number.NEGATIVE_INFINITY
}

// Newest photo first. The sort is stable, so pins taken at the same time keep the order they came in.
export function newestFirst(pins: readonly Pin[]): Pin[] {
  return [...pins].sort((a, b) => {
    const [x, y] = [takenAt(a), takenAt(b)]
    return x === y ? 0 : x < y ? 1 : -1
  })
}

// The other live pins within 300 m, taken in the last 3 hours. Not the pin itself, and no demo pin, which is a photo of
// another day and says nothing about now.
export function nearbyCount(pin: Pin, pins: readonly Pin[], now: Date): number {
  return pins.filter(
    (other) =>
      other.id !== pin.id &&
      other.mode === 'live' &&
      pinStrength(other, now) !== 'gone' &&
      distanceM(pin, other) <= NEARBY_M,
  ).length
}

// ---- what the visit remembers, in memory only ----

// The highest flag count seen for each pin, from the map's reads and from a flag's answers alike. A flag's answer can
// lag behind the last one (amendment 9), so a count never shows lower than one the person has already seen.
const highestFlags = new Map<string, number>()
// The pins this phone has flagged in this visit. The API keeps one flag per phone, so a repeat only returns its count.
const flagged = new Set<string>()

export function flagCount(id: string, n: number): number {
  const count = Number.isFinite(n) && n > 0 ? Math.floor(n) : 0
  const highest = Math.max(count, highestFlags.get(id) ?? 0)
  highestFlags.set(id, highest)
  return highest
}

export function markFlagged(id: string): void {
  flagged.add(id)
}

export function wasFlagged(id: string): boolean {
  return flagged.has(id)
}

// For the tests: a new visit.
export function resetPinMemory(): void {
  highestFlags.clear()
  flagged.clear()
}
