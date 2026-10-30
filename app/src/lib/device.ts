// The random device id (spec C606) for MS4's hourly limits, sent as X-Lusot-Device with uploads, samples and
// flags. Made once with crypto.randomUUID() and kept in lusot.device (C607). Never shown or logged.
import { readItem, writeItem } from './storage'

const KEY = 'lusot.device'
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/

// Kept for the session too, so the id stays the same when storage can't keep it.
let sessionId: string | undefined

export function getDeviceId(): string {
  if (sessionId === undefined) {
    const stored = readItem(KEY)
    sessionId = stored !== null && UUID.test(stored) ? stored : newUuid()
    if (sessionId !== stored) writeItem(KEY, sessionId)
  }
  return sessionId
}

// crypto.randomUUID() exists only in a secure context. Over plain http (a LAN IP from the dev server), a
// version-4 UUID is built from getRandomValues, which works there, in the same form MS4 accepts.
function newUuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40 // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80 // variant 10
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
