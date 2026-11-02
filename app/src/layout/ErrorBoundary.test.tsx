import { cleanup, render, screen, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { EN } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { LanguageProvider } from '../i18n'
import { writeItem } from '../lib/storage'
import type { Route } from '../router'
import { ErrorBoundary } from './ErrorBoundary'
import { Layout } from './Layout'

const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'

function Broken(): never {
  throw new Error('This screen is broken on purpose.')
}

beforeEach(() => {
  // React reports a caught render error to the console. The tests throw on purpose, so keep that out of the log.
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('lang')
})

it('shows a short plain line, as an alert, where a child that throws would have been', () => {
  render(
    <LanguageProvider>
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>
    </LanguageProvider>,
  )

  const alert = screen.getByRole('alert')
  expect(alert.textContent).toBe(EN['layout.errorFallback'].text)
  expect(alert.textContent).not.toMatch(/safe|ligtas/i)
  expect(alert.textContent).not.toContain('broken on purpose')
})

it('renders its children untouched when none throws', () => {
  render(
    <LanguageProvider>
      <ErrorBoundary>
        <p>A working screen</p>
      </ErrorBoundary>
    </LanguageProvider>,
  )

  expect(screen.getByText('A working screen')).toBeTruthy()
  expect(screen.queryByRole('alert')).toBeNull()
})

it('says it in Taglish on a Taglish screen, now that both lines are reviewed', () => {
  writeItem('lusot.lang', 'fil')

  render(
    <LanguageProvider>
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>
    </LanguageProvider>,
  )

  expect(screen.getByRole('alert').textContent).toBe(FIL['layout.errorFallback'].text)
  expect(EN['layout.errorFallback'].reviewed).toBe(true)
  expect(FIL['layout.errorFallback'].reviewed).toBe(true)
})

// The layout puts the boundary around the screen inside <main>, so a crash costs only the screen (S5-R5).
function inLayout(route: Route, screenElement: ReactNode) {
  return (
    <LanguageProvider>
      <Layout route={route} apiReady>
        {screenElement}
      </Layout>
    </LanguageProvider>
  )
}

it('keeps the header, the nav and the screen line when the screen crashes, and shows the line in the screen', () => {
  render(inLayout({ name: 'map' }, <Broken />))

  const main = screen.getByRole('main')
  expect(within(main).getByRole('alert').textContent).toBe(EN['layout.errorFallback'].text)
  expect(within(screen.getByRole('banner')).getByText('Lusot')).toBeTruthy()
  // The page draws the nav twice, in the header for lg and in the footer below it (Layout.test.tsx); each has the five links.
  expect(screen.getAllByRole('navigation').map((nav) => within(nav).getAllByRole('link').length)).toEqual([5, 5])
  const line = screen.getByText(SCREEN_LINE)
  expect(line.getAttribute('lang')).toBe('en')
  expect(main.contains(line)).toBe(false)
  expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
})

it('recovers when the person goes to another screen', () => {
  const { rerender } = render(inLayout({ name: 'map' }, <Broken />))
  expect(screen.getByRole('alert')).toBeTruthy()

  rerender(inLayout({ name: 'tested' }, <p>The Tested screen</p>))

  expect(screen.getByText('The Tested screen')).toBeTruthy()
  expect(screen.queryByRole('alert')).toBeNull()
})
