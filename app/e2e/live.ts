// What MS7's live pass shares (MS7 Task 10, C820): the site's address, the marks the app keeps on the phone, the guard
// that keeps every request a read, and the map's first pin. The live specs run against a deployed site, or a local
// preview or MS5's in-page mock, never against MS5's end-to-end mocks, and they never type a pin's id into a title or a
// message: a pin's id is its report id (MS4's C504), which no output may hold (MS7's C812).
import { readFileSync } from 'node:fs'
import type { Page } from '@playwright/test'

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
  await page.route('**/*', async (route) => {
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

// The first pin of the app's own map read (GET /map/pins, which holds demo pins too, MS4's C519), or, with MS5's
// in-page mock, which makes no request, the first pin of the map's list; null when there is none. `opened` is the
// page's navigation to #/map, started after this is called, so the read can't be missed.
export async function firstPin(page: Page, opened: () => Promise<unknown>, listLabel: string): Promise<string | null> {
  const read = page
    .waitForResponse((r) => r.request().method() === 'GET' && new URL(r.url()).pathname.endsWith('/map/pins'), {
      timeout: 15_000,
    })
    .catch(() => null)
  await opened()
  const response = await read
  if (response !== null && response.ok()) {
    const body: unknown = await response.json().catch(() => null)
    const pins = (body as { pins?: unknown } | null)?.pins
    if (Array.isArray(pins)) {
      for (const pin of pins) {
        const id = (pin as { id?: unknown } | null)?.id
        if (typeof id === 'string' && PIN_ID.test(id)) return id
      }
    }
    return null
  }
  // No map read reached the network: MS5's mock, or a build without an API.
  const list = page.getByRole('button', { name: listLabel, exact: true })
  if ((await list.count()) === 0) return null
  await list.click()
  const link = page.locator('a[href^="#/pin/"]').first()
  if ((await link.count()) === 0) return null
  const id = (await link.getAttribute('href'))?.slice('#/pin/'.length) ?? ''
  return PIN_ID.test(id) ? id : null
}
