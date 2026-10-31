// What MS7's live pass shares (MS7 Task 10, C820): the site's address, the marks the app keeps on the phone, the guard
// that keeps every request a read, and the map's first pin. The live specs run against a deployed site, or a local
// preview or MS5's in-page mock, never against MS5's end-to-end mocks, and they never type a pin's id into a title or a
// message: a pin's id is its report id (MS4's C504), which no output may hold (MS7's C812).
import { readFileSync } from 'node:fs'
import type { Page, Response } from '@playwright/test'

export const LIVE_URL = process.env.LUSOT_LIVE_URL ?? ''
export const SKIP_REASON = 'set LUSOT_LIVE_URL to the site to run the live pass'

// The keys the app keeps in localStorage: the language (app/src/i18n/index.tsx) and the gates' marks
// (app/src/lib/consent.tsx, C607), { adult: true, notice: <version> }.
export const LANG_KEY = 'lusot.lang'
export const CONSENT_KEY = 'lusot.consent'

// The notice's version, as the app computes it: FNV-1a, 32 bits, over consent.en.md's UTF-8 text, as 8 hex digits.
// A site built from another notice asks again, which the screen-line spec reports on #/report.
export function fnv1a32(text: string): string {
  let hash = 0x811c9dc5
  for (const byte of new TextEncoder().encode(text)) hash = Math.imul(hash ^ byte, 0x01000193) >>> 0
  return hash.toString(16).padStart(8, '0')
}
export const NOTICE_VERSION = fnv1a32(readFileSync(new URL('../src/content/consent.en.md', import.meta.url), 'utf8'))

// Requests that only read. Anything else (POST /uploads, POST /samples/{id}, POST /ask and POST /ask/voice among
// them, each of which can reach Meta) is aborted before it leaves the browser, and recorded.
const READS = new Set(['GET', 'HEAD', 'OPTIONS'])

// A request's method and path, with any part that could be an id shown as <id>, so a recorded request names no report.
function described(method: string, url: string): string {
  let path = url
  try {
    path = new URL(url).pathname
  } catch {
    // not a URL: keep the method only
    return method
  }
  const parts = path.split('/').map((part) => (/^[a-z]+$/.test(part) || part === '' ? part : '<id>'))
  return `${method} ${parts.join('/')}`
}

// Routes every request of the page through the guard; returns the list of requests it stopped.
export async function guardWrites(page: Page): Promise<string[]> {
  const stopped: string[] = []
  // The context's route, so a popup the page opens is guarded too.
  await page.context().route('**/*', async (route) => {
    const request = route.request()
    if (READS.has(request.method())) {
      await route.continue()
      return
    }
    stopped.push(described(request.method(), request.url()))
    await route.abort('blockedbyclient')
  })
  return stopped
}

const PIN_ID = /^[A-Za-z0-9_-]{1,64}$/

// Strict on a real site: a step the site can't show fails instead of skipping, so a broken or stale deploy (a failed
// GET /samples reads as an empty list, a build with no API hides Ask) can't pass as "skipped". On by default unless
// the site is on this machine; LUSOT_LIVE_STRICT=1 or 0 overrides.
function isLocal(url: string): boolean {
  try {
    return ['localhost', '127.0.0.1', '[::1]'].includes(new URL(url).hostname)
  } catch {
    return false
  }
}
export const STRICT = process.env.LUSOT_LIVE_STRICT === undefined ? !isLocal(LIVE_URL) : process.env.LUSOT_LIVE_STRICT === '1'

// The app's own map read (GET /map/pins, which holds demo pins too, MS4's C519), watched from before the page opens
// so it can't be missed; null when none reaches the network in 15 s (MS5's in-page mock, or a build with no API).
export function mapRead(page: Page): Promise<Response | null> {
  return page
    .waitForResponse((r) => r.request().method() === 'GET' && new URL(r.url()).pathname.endsWith('/map/pins'), {
      timeout: 15_000,
    })
    .catch(() => null)
}

// The first pin of that read, or, with no read on the network, of the map's list (MS5's in-page mock); null when there
// is none. A failed read throws with its status only. The id is never printed: it is a report id.
export async function firstPin(page: Page, read: Response | null, listLabel: string): Promise<string | null> {
  if (read !== null) {
    if (!read.ok()) throw new Error(`the app's map read answered ${read.status()}`)
    const body: unknown = await read.json().catch(() => null)
    const pins = (body as { pins?: unknown } | null)?.pins
    if (!Array.isArray(pins)) throw new Error("the app's map read holds no pins list")
    for (const pin of pins) {
      const id = (pin as { id?: unknown } | null)?.id
      if (typeof id === 'string' && PIN_ID.test(id)) return id
    }
    return null
  }
  if (STRICT) throw new Error('the app made no map read on the network')
  const list = page.getByRole('button', { name: listLabel, exact: true })
  if ((await list.count()) === 0) return null
  await list.click()
  const link = page.locator('a[href^="#/pin/"]').first()
  if ((await link.count()) === 0) return null
  const id = (await link.getAttribute('href'))?.slice('#/pin/'.length) ?? ''
  return PIN_ID.test(id) ? id : null
}

// Opens a pin's screen without its id in any URL Playwright prints: the page starts on the map, then its hash is set
// in the page, so a failure names the map's address only.
export async function openPin(page: Page, id: string): Promise<void> {
  await page.goto('about:blank')
  await page.goto('#/map')
  await page.evaluate((pin) => {
    window.location.hash = `#/pin/${pin}`
  }, id)
}
