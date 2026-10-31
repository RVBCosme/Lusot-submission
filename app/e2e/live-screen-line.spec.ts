// MS7's live pass (MS7 Task 10, C820): on the site that LUSOT_LIVE_URL names, CLAUDE.md's exact screen line is in the
// viewport, on top and in English, at 360 x 640, in English and Taglish, on every read-only route of MS5's router:
// the map, Tested, About, the privacy page, the licences page, the report flow's first step, Ask Lusot, and one pin's
// screen when the app's map read holds a pin. #/report opens with the 18+ and consent marks already set, so its
// camera step is what is checked, and nothing is ever sent: the guard aborts any request that isn't a read.
//
// Skipped unless LUSOT_LIVE_URL is set. A pin's id is a report id, so no title or message ever holds it.
import { expect, test } from '@playwright/test'
import { CONSENT_KEY, firstPin, guardWrites, LANG_KEY, LIVE_URL, NOTICE_VERSION, SKIP_REASON } from './live'
import { expectLine, LINE } from './screenLine'
import { label, type Lang } from './steps'

test.skip(LIVE_URL === '', SKIP_REASON)

// MS5's router (app/src/router.ts): every page it names. #/pin/<id> joins when the map read holds a pin.
const ROUTES = ['#/map', '#/tested', '#/about', '#/privacy', '#/licences', '#/report', '#/ask'] as const

const LANGS: { lang: Lang; name: string }[] = [
  { lang: 'en', name: 'English' },
  { lang: 'fil', name: 'Taglish' },
]

for (const { lang, name } of LANGS) {
  test(`the screen line is in view on every read-only route, 360 x 640, ${name}`, async ({ page }) => {
    const stopped = await guardWrites(page)
    await page.addInitScript(
      ({ langKey, chosen, consentKey, consent }) => {
        localStorage.setItem(langKey, chosen)
        localStorage.setItem(consentKey, consent)
      },
      { langKey: LANG_KEY, chosen: lang, consentKey: CONSENT_KEY, consent: JSON.stringify({ adult: true, notice: NOTICE_VERSION }) },
    )

    // Each route opens as a fresh page load, as a link to it would.
    const open = async (hash: string) => {
      await page.goto('about:blank')
      await page.goto(hash)
    }
    const check = async (where: string) => {
      await expect(page.locator('html'), `${where}: the page is in ${name}`).toHaveAttribute('lang', lang)
      const line = page.getByText(LINE, { exact: true })
      await expect(line, `${where}: the page holds the screen line once`).toHaveCount(1)
      await expect(line, `${where}: the screen line is wholly inside the viewport`).toBeInViewport({ ratio: 1 })
      await expectLine(page, `${where}, ${name}`)
    }

    let pin: string | null = null
    for (const hash of ROUTES) {
      await test.step(hash, async () => {
        if (hash === '#/map') pin = await firstPin(page, () => open(hash), label(lang, 'map.list'))
        else await open(hash)
        await check(hash)
        if (hash === '#/report') {
          await expect(page.getByTestId('notice'), '#/report: the marks hold, so the notice stays closed').toBeHidden()
        }
      })
    }
    await test.step('#/pin (the first pin of the map read)', async (step) => {
      step.skip(pin === null, 'the map read holds no pin')
      if (pin === null) return
      await open(`#/pin/${pin}`)
      await check('#/pin')
    })

    expect(stopped, 'every request was a read').toEqual([])
  })
}
