import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import consentText from '../content/consent.en.md?raw'
import { LanguageProvider } from '../i18n'
import { EN } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { writeItem } from '../lib/storage'
import { ConsentScreen } from './ConsentScreen'

const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
const NOT_AFFILIATED = 'Not affiliated with MMDA.'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  history.replaceState(null, '', '/')
  document.documentElement.removeAttribute('lang')
})

function renderScreen(kind: 'adult' | 'notice', { lang = 'en' }: { lang?: 'en' | 'fil' } = {}) {
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  const onContinue = vi.fn()
  const onCancel = vi.fn()
  render(
    <LanguageProvider>
      <ConsentScreen kind={kind} onContinue={onContinue} onCancel={onCancel} />
    </LanguageProvider>,
  )
  return { onContinue, onCancel }
}

const continueButton = () => screen.getByRole('button', { name: EN['consent.continue'].text }) as HTMLButtonElement
// The notice's own text, rendered from consent.en.md.
const notice = () => screen.getByTestId('notice')

describe.each(['adult', 'notice'] as const)('the %s screen', (kind) => {
  it('"Continue" is disabled until the 18+ box is checked, and again once it is cleared', () => {
    const { onContinue } = renderScreen(kind)
    const box = screen.getByRole('checkbox', { name: /I am 18 or older\./ }) as HTMLInputElement

    expect(box.checked).toBe(false)
    expect(continueButton().disabled).toBe(true)
    fireEvent.click(continueButton())
    expect(onContinue).not.toHaveBeenCalled()

    fireEvent.click(box)
    expect(continueButton().disabled).toBe(false)
    fireEvent.click(box)
    expect(continueButton().disabled).toBe(true)

    fireEvent.click(box)
    fireEvent.click(continueButton())
    expect(onContinue).toHaveBeenCalledTimes(1)
  })

  it('"Not now" cancels, checked box or not, and never continues', () => {
    const { onContinue, onCancel } = renderScreen(kind)
    fireEvent.click(screen.getByRole('button', { name: EN['consent.notNow'].text }))
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: EN['consent.notNow'].text }))

    expect(onCancel).toHaveBeenCalledTimes(2)
    expect(onContinue).not.toHaveBeenCalled()
  })

  it('carries "Not affiliated with MMDA." and a link to the privacy policy', () => {
    renderScreen(kind)
    expect(screen.getByText(NOT_AFFILIATED)).toBeTruthy()
    expect(screen.getByRole('link', { name: EN['consent.readPolicy'].text }).getAttribute('href')).toBe('#/privacy')
  })

  it('has one heading at level 1, one checkbox, and touch targets from the tokens', () => {
    renderScreen(kind)
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getAllByRole('checkbox')).toHaveLength(1)
    for (const button of screen.getAllByRole('button')) expect(button.className).toContain('min-h-tap')
    expect(screen.getByRole('checkbox').closest('label')?.className).toContain('min-h-tap')
  })
})

describe('the notice', () => {
  it("shows consent.en.md's heading and bullets, and no checkbox, button, link or screen line from the Markdown", () => {
    renderScreen('notice')

    expect(within(notice()).getByRole('heading', { level: 1 }).textContent).toBe('Before your first photo or question')
    expect(within(notice()).getAllByRole('listitem')).toHaveLength(7)
    expect(notice().querySelector('input, button, a')).toBeNull()
    expect(notice().textContent).not.toContain(SCREEN_LINE)
    expect(notice().textContent).not.toContain(NOT_AFFILIATED)
    expect(consentText).not.toMatch(/\[ \]|\[Continue\]|\[Not now\]|Read the privacy policy/)
  })

  it('on #/report, the page holds the screen line once, in the bar, not in the notice', () => {
    history.replaceState(null, '', '/#/report')
    render(<App apiUrl="https://api.example.test" />)

    expect(notice()).toBeTruthy()
    expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
    expect(screen.getByRole('main').textContent).not.toContain(SCREEN_LINE)
    expect(screen.getAllByText(NOT_AFFILIATED)).toHaveLength(1)
  })

  // What CLAUDE.md's privacy rules and Rene's Oct 29 and 30 decisions require the notice to say.
  it.each([
    ['the photo goes to Meta', /Your photo goes to Meta\./],
    ['faces are blurred first', /Lusot first blurs faces automatically on its own server\./],
    ['Meta may use it to improve its products', /may use it to improve its products/],
    ['plates reach Meta and are blurred before storage', /Licence plates aren't blurred before Meta receives the photo, only before Lusot stores it/],
    ['the original is deleted after analysis', /Your original waits in a private storage area until the analysis ends, and is then deleted\./],
    ['data is kept 7 days', /for 7 days/],
    ['the map images show OpenStreetMap the area, within about 300 m', /Placing the pin loads OpenStreetMap's map images[^.]*the area on your screen, within about 300 m of you\./],
    ['a spoken question goes to Meta as a voice clip', /for a spoken question, its voice clip of up to 15 seconds, which Meta's speech service turns into text\./],
    ['no accounts, no names', /No accounts, no names\./],
  ])('says %s', (_what, pattern) => {
    renderScreen('notice')
    expect(notice().textContent).toMatch(pattern)
  })

  it('in Taglish, shows the notice in English, marked lang="en", and its controls in their reviewed Taglish', () => {
    renderScreen('notice', { lang: 'fil' })

    expect(notice().getAttribute('lang')).toBe('en')
    expect(within(notice()).getByRole('heading', { level: 1 }).textContent).toBe('Before your first photo or question')
    // The M20 review passed the controls' Taglish, so they show it unmarked, as the page's own language.
    for (const key of ['consent.continue', 'consent.notNow', 'consent.readPolicy', 'consent.adult'] as const) {
      expect(FIL[key].reviewed, key).toBe(true)
      const line = screen.getByText(FIL[key].text)
      expect(line.closest('[lang="en"]'), key).toBeNull()
      expect(line.closest('[lang]')?.getAttribute('lang'), key).toBe('fil')
    }
    expect(screen.getByText(NOT_AFFILIATED).closest('[lang]')?.getAttribute('lang')).toBe('en')
  })

  it('in Taglish, shows a control whose Taglish is not reviewed in English, marked lang="en"', () => {
    const reviewed = FIL['consent.continue']
    FIL['consent.continue'] = { ...reviewed, reviewed: false }
    try {
      renderScreen('notice', { lang: 'fil' })
      const line = screen.getByText(EN['consent.continue'].text)
      expect(line.closest('[lang]')?.getAttribute('lang')).toBe('en')
      expect(screen.queryByText(reviewed.text)).toBeNull()
    } finally {
      FIL['consent.continue'] = reviewed
    }
  })
})

describe('the 18+ check', () => {
  it('says Lusot is only for adults, and shows no notice', () => {
    renderScreen('adult')
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(EN['consent.adultTitle'].text)
    expect(screen.getByText(EN['consent.adultBody'].text)).toBeTruthy()
    expect(screen.queryByTestId('notice')).toBeNull()
  })
})
