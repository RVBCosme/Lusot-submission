// Ask Lusot's screen end to end (its plan Task 16), against mocks.ts's answers, in the `ask` project, whose microphone
// plays a 2 s tone (e2e/tone.ts): a typed question shows its cards, each a link to its pin; the fake microphone records,
// and the transcript and the answer appear, with the clip the app sent checked as the 16 kHz mono 16-bit WAV the API
// takes; and at 360 x 640 and 390 x 844, in both themes and both languages, the screen line is on top, before and with an
// answer. Each of those screens is saved for review in the git-ignored test-results.
import { ASK_TRANSCRIPT } from '../src/mock/fixtures'
import { expect, test } from './mocks'
import { expectLine } from './screenLine'
import { acceptNotice, label, type Lang } from './steps'

const QUESTION = 'Gaano kalalim ang baha sa España cor. Maceda?'
const SUMMARY = /^3 reports within 300 m of España Blvd cor\. Maceda St in the last 3 hours\.$/

test('a typed question shows its cards, each a link to its pin', async ({ page, mocks }) => {
  await page.goto('/#/ask')
  await page.getByRole('textbox', { name: label('en', 'ask.ui.questionLabel') }).fill(QUESTION)
  await page.getByRole('button', { name: label('en', 'ask.ui.send'), exact: true }).click()
  // The first question of a visit meets the notice (C605).
  await acceptNotice(page, 'en')

  const answer = page.getByRole('region', { name: label('en', 'ask.ui.answer') })
  await expect(answer.getByText(SUMMARY)).toBeVisible()
  const links = answer.getByRole('link')
  await expect(links).toHaveCount(4) // three live reports and a demo pin
  for (const href of await links.evaluateAll((all) => all.map((a) => a.getAttribute('href')))) {
    expect(href).toMatch(/^#\/pin\/r_[0-9a-f]{32}$/)
  }
  await expect(answer.getByText(label('en', 'ask.answer.demo'))).toBeVisible()

  const asked = mocks.requests.filter((request) => request.path === '/ask')
  expect(asked).toHaveLength(1)
  expect(asked[0]?.json).toEqual({ question: QUESTION })
  expect(asked[0]?.headers['x-lusot-device']).toMatch(/\S/)
})

test('the fake microphone records, and the transcript and the answer appear', async ({ page, mocks }) => {
  await page.goto('/#/ask')
  await page.getByRole('button', { name: label('en', 'ask.ui.mic') }).click()
  await acceptNotice(page, 'en')

  // The countdown follows the audio the worklet hands over, so reaching 13 s left means about 2 s were recorded.
  const timer = page.getByRole('timer')
  await expect(timer).toHaveText(label('en', 'ask.ui.micLeft', { s: 13 }))
  await page.getByRole('button', { name: label('en', 'ask.ui.micStop') }).click()

  const answer = page.getByRole('region', { name: label('en', 'ask.ui.answer') })
  await expect(answer.getByText(label('en', 'ask.ui.youAsked'))).toBeVisible()
  await expect(answer.getByText(ASK_TRANSCRIPT, { exact: true })).toBeVisible()
  await expect(answer.getByText(SUMMARY)).toBeVisible()
  await expect(page.getByRole('button', { name: label('en', 'ask.ui.mic') })).toBeEnabled()

  // The clip: RIFF/WAVE, PCM, mono, 16-bit at 16 kHz, about 2 s long, and holding the tone, not silence.
  const spoken = mocks.requests.filter((request) => request.path === '/ask/voice')
  expect(spoken).toHaveLength(1)
  const { audio } = (spoken[0]?.json ?? {}) as { audio?: string }
  const wav = Buffer.from(audio ?? '', 'base64')
  expect([wav.toString('ascii', 0, 4), wav.toString('ascii', 8, 16), wav.toString('ascii', 36, 40)]).toEqual(['RIFF', 'WAVEfmt ', 'data'])
  expect([wav.readUInt16LE(20), wav.readUInt16LE(22), wav.readUInt32LE(24), wav.readUInt16LE(34)]).toEqual([1, 1, 16000, 16])
  const seconds = wav.readUInt32LE(40) / 32000
  expect(seconds).toBeGreaterThan(1.5)
  expect(seconds).toBeLessThan(6)
  let peak = 0
  for (let at = 44; at + 1 < wav.length; at += 2) peak = Math.max(peak, Math.abs(wav.readInt16LE(at)))
  expect(peak / 32768).toBeGreaterThan(0.01)
})

const SIZES = [
  { width: 360, height: 640 },
  { width: 390, height: 844 },
]
const THEMES = ['light', 'dark'] as const
const LANGS: { lang: Lang; name: string }[] = [
  { lang: 'en', name: 'English' },
  { lang: 'fil', name: 'Taglish' },
]

for (const size of SIZES) {
  for (const theme of THEMES) {
    for (const { lang, name } of LANGS) {
      const where = `${size.width} x ${size.height}, ${theme}, ${name}`
      test(`the screen line is on top on the Ask screen, ${where}`, async ({ page }, testInfo) => {
        await page.setViewportSize(size)
        await page.emulateMedia({ colorScheme: theme })
        await page.addInitScript((chosen) => localStorage.setItem('lusot.lang', chosen), lang)

        await page.goto('/#/ask')
        await expect(page.getByRole('heading', { name: label(lang, 'nav.ask'), level: 1 })).toBeVisible()
        expect(await page.evaluate(() => matchMedia('(prefers-color-scheme: dark)').matches)).toBe(theme === 'dark')
        await expectLine(page, `${where}, empty`)
        await page.screenshot({ path: testInfo.outputPath(`ask-empty-${size.width}x${size.height}-${theme}-${lang}.png`) })

        await page.getByRole('textbox', { name: label(lang, 'ask.ui.questionLabel') }).fill('Lusot ba sedan ko sa España cor. Maceda?')
        await page.getByRole('button', { name: label(lang, 'ask.ui.send'), exact: true }).click()
        await acceptNotice(page, lang)
        await expect(page.getByRole('region', { name: label(lang, 'ask.ui.answer') })).toBeVisible()
        await expectLine(page, `${where}, an answer`)
        await page.screenshot({ path: testInfo.outputPath(`ask-answer-${size.width}x${size.height}-${theme}-${lang}.png`) })
      })
    }
  }
}
