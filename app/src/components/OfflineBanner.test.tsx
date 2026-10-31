import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../i18n'
import { EN } from '../i18n/en'
import { OfflineBanner } from './OfflineBanner'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const LINE = EN['layout.offline'].text

it('shows on an offline event and hides on online', () => {
  render(
    <LanguageProvider>
      <OfflineBanner />
    </LanguageProvider>,
  )
  expect(screen.queryByText(LINE)).toBeNull()
  act(() => {
    window.dispatchEvent(new Event('offline'))
  })
  expect(screen.getByRole('status').textContent).toBe(LINE)
  act(() => {
    window.dispatchEvent(new Event('online'))
  })
  expect(screen.queryByText(LINE)).toBeNull()
})

it('shows at once when the app opens offline', () => {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
  render(
    <LanguageProvider>
      <OfflineBanner />
    </LanguageProvider>,
  )
  expect(screen.getByText(LINE)).toBeTruthy()
})
