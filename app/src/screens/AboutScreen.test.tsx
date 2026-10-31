import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { LanguageProvider } from '../i18n'
import { EN, type StringKey } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { applyTheme, storedTheme } from '../lib/theme'
import { AboutScreen } from './AboutScreen'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  history.replaceState(null, '', '/')
  document.documentElement.removeAttribute('lang')
  document.documentElement.removeAttribute('data-theme')
})

function renderAbout() {
  return render(
    <LanguageProvider>
      <AboutScreen />
    </LanguageProvider>,
  )
}

const text = (key: StringKey) => EN[key].text

describe('About', () => {
  it('says what Lusot is, and carries the credits and "Not affiliated with MMDA."', () => {
    renderAbout()

    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(text('nav.about'))
    expect(screen.getByText(text('about.what'))).toBeTruthy()
    const credits = screen.getByRole('region', { name: text('about.creditsTitle') })
    for (const key of ['about.credits.maker', 'about.credits.models', 'about.credits.levels'] as const) {
      expect(within(credits).getByText(text(key)), key).toBeTruthy()
    }
    expect(screen.getAllByText('Not affiliated with MMDA.')).toHaveLength(1)
  })

  it('links to the privacy policy, the licences, MMDA and PAGASA', () => {
    renderAbout()
    const href = (name: string) => screen.getByRole('link', { name }).getAttribute('href')

    expect(href(text('privacy.title'))).toBe('#/privacy')
    expect(href(text('licences.title'))).toBe('#/licences')
    expect(href(text('about.mmda'))).toBe('https://mmda.gov.ph/')
    expect(href(text('about.pagasa'))).toBe('https://www.pagasa.dost.gov.ph/')
  })

  it('holds the language switch, which switches the language', () => {
    renderAbout()
    const group = screen.getByRole('group', { name: text('lang.switch') })

    fireEvent.click(within(group).getByRole('button', { name: FIL['lang.fil'].text }))

    expect(document.documentElement.lang).toBe('fil')
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(FIL['nav.about'].text)
  })

  it("the language switch's pressed state keeps its text's contrast: no fade, an ink fill from the tokens (S5-R6)", () => {
    renderAbout()
    for (const button of within(screen.getByRole('group', { name: text('lang.switch') })).getAllByRole('button')) {
      expect(button.className).not.toMatch(/opacity/)
      expect(button.className).toContain('active:bg-ink')
      expect(button.className).toContain('active:text-surface')
    }
  })
})

describe('the theme choice', () => {
  const radio = (key: StringKey) => screen.getByRole('radio', { name: text(key) }) as HTMLInputElement

  it('offers the system, light and dark, follows the system at first, and sets data-theme and lusot.theme', () => {
    renderAbout()
    const group = screen.getByRole('group', { name: text('about.theme') })
    expect(within(group).getAllByRole('radio')).toHaveLength(3)
    expect(radio('about.theme.system').checked).toBe(true)
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)

    fireEvent.click(radio('about.theme.dark'))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('lusot.theme')).toBe('dark')
    expect(radio('about.theme.dark').checked).toBe(true)

    fireEvent.click(radio('about.theme.light'))
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('lusot.theme')).toBe('light')

    fireEvent.click(radio('about.theme.system'))
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
    expect(localStorage.getItem('lusot.theme')).toBe('system')
  })

  it('shows the theme in use when About opens', () => {
    applyTheme('dark')
    renderAbout()
    expect(radio('about.theme.dark').checked).toBe(true)
  })

  it('reads a stored choice, and anything else as the system', () => {
    expect(storedTheme()).toBe('system')
    localStorage.setItem('lusot.theme', 'dark')
    expect(storedTheme()).toBe('dark')
    localStorage.setItem('lusot.theme', 'light')
    expect(storedTheme()).toBe('light')
    localStorage.setItem('lusot.theme', 'sepia')
    expect(storedTheme()).toBe('system')
  })

  it('with storage blocked, the choice still applies for the session', () => {
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new DOMException('The operation is insecure.', 'SecurityError')
    })
    expect(storedTheme()).toBe('system')
    renderAbout()

    fireEvent.click(radio('about.theme.dark'))

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(radio('about.theme.dark').checked).toBe(true)
  })

  it('every option has a touch target from the tokens', () => {
    renderAbout()
    for (const key of ['about.theme.system', 'about.theme.light', 'about.theme.dark'] as const) {
      expect(radio(key).closest('label')?.className, key).toContain('min-h-tap')
    }
  })
})

it('#/about in the app shows About with the screen line once', () => {
  history.replaceState(null, '', '/#/about')
  render(<App apiUrl="https://api.example.test" />)
  const line = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'

  expect(screen.getByText(text('about.what'))).toBeTruthy()
  expect(document.body.textContent?.split(line)).toHaveLength(2)
})
