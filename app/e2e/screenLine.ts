// The screen-line check the end-to-end specs share (MS5 Task 18, Review Focus 3; Ask Lusot's Task 16): the line must be
// in the viewport and on top, which `document.elementFromPoint` at its centre and both ends proves, since a stacking
// mistake would hide the line while it stayed "in the viewport".
import { expect, type Page } from '@playwright/test'

export const LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'

type LineReading = { inView: boolean; onTop: boolean; inDialog: boolean; lang: string | null }

// Every paragraph that is the screen line, as the browser sees it now.
export function readLines(page: Page): Promise<LineReading[]> {
  return page.evaluate((line) => {
    const readings: LineReading[] = []
    for (const el of document.querySelectorAll('p')) {
      if (el.textContent?.trim() !== line) continue
      const box = el.getBoundingClientRect()
      const inView =
        box.width > 0 &&
        box.height > 0 &&
        box.top >= 0 &&
        box.left >= 0 &&
        box.bottom <= window.innerHeight &&
        box.right <= window.innerWidth
      const y = box.top + box.height / 2
      const onTop =
        inView &&
        [box.left + box.width / 2, box.left + 2, box.right - 2].every((x) => {
          const hit = document.elementFromPoint(x, y)
          return hit !== null && (hit === el || el.contains(hit))
        })
      readings.push({ inView, onTop, inDialog: el.closest('dialog') !== null, lang: el.getAttribute('lang') })
    }
    return readings
  }, LINE)
}

// The line is inside the viewport and on top, and stays English (C619). An open flag dialog is a modal <dialog> in the
// browser's top layer, over the bar, so it carries its own line (S5-R5): there are two on the page, and the dialog's is the
// one on top.
export async function expectLine(page: Page, where: string, dialog = false): Promise<void> {
  const lines = await readLines(page)
  const shown = lines.filter((reading) => reading.inView && reading.onTop)
  expect.soft(shown.length, `${where}: the screen line is inside the viewport and on top`).toBeGreaterThan(0)
  expect.soft(lines.length, `${where}: how many screen lines the page holds`).toBe(dialog ? 2 : 1)
  if (dialog) expect.soft(shown.some((reading) => reading.inDialog), `${where}: the dialog's own line is the one on top`).toBe(true)
  for (const reading of shown) expect.soft(reading.lang, `${where}: the line is marked English`).toBe('en')
}
