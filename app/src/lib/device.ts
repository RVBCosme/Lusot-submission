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
    sessionId = stored !== null && UUID.test(stored) ? stored : crypto.randomUUID()
    if (sessionId !== stored) writeItem(KEY, sessionId)
  }
  return sessionId
}
