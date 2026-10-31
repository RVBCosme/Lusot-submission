import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../../i18n'
import { EN, type StringKey } from '../../i18n/en'
import { FIL } from '../../i18n/fil'
import { writeItem } from '../../lib/storage'
import { CheckStep } from './CheckStep'

const DARK = { brightness: 12.5, sharpness: 300 }
const BLURRY = { brightness: 120, sharpness: 3 }

afterEach(() => {
  cleanup()
  localStorage.clear()
})

function renderCheck(props: Partial<Parameters<typeof CheckStep>[0]> = {}, lang: 'en' | 'fil' = 'en') {
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  const onRetake = vi.fn()
  const onSend = vi.fn()
  render(
    <LanguageProvider>
      <CheckStep scores={DARK} smallStill={false} onRetake={onRetake} onSend={onSend} {...props} />
    </LanguageProvider>,
  )
  return { onRetake, onSend }
}

const en = (key: StringKey) => EN[key].text

describe('the phone\'s quality check (C604)', () => {
  it('a dark photo shows the retake tip, with "Retake" first and "Send anyway" second', () => {
    const { onRetake, onSend } = renderCheck()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(en('report.checkTitle'))
    expect(screen.getByText(en('retake.too_dark'))).toBeTruthy()
    expect(screen.queryByText(en('retake.too_blurry'))).toBeNull()
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([en('report.retake'), en('report.sendAnyway')])
    fireEvent.click(screen.getByRole('button', { name: en('report.retake') }))
    expect(onRetake).toHaveBeenCalledTimes(1)
    expect(onSend).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: en('report.sendAnyway') }))
    expect(onSend).toHaveBeenCalledTimes(1)
  })

  it('a blurry photo shows the blur tip', () => {
    renderCheck({ scores: BLURRY })
    expect(screen.getByText(en('retake.too_blurry'))).toBeTruthy()
    expect(screen.queryByText(en('retake.too_dark'))).toBeNull()
  })

  it('says the server checks again, so the photo can still be sent', () => {
    renderCheck()
    expect(screen.getByText(en('report.checkNote'))).toBeTruthy()
  })

  it('with a small still, shows the small-photo warning too', () => {
    renderCheck({ smallStill: true })
    expect(screen.getByText(en('report.smallStill'))).toBeTruthy()
  })

  it('in Taglish, the tip stays English and marked so until its Taglish is reviewed (C619)', () => {
    renderCheck({}, 'fil')
    expect(FIL['retake.too_dark'].reviewed).toBe(false)
    const tip = screen.getByText(en('retake.too_dark'))
    expect(tip.closest('[lang]')?.getAttribute('lang')).toBe('en')
    expect(screen.getByRole('button', { name: FIL['report.sendAnyway'].text })).toBeTruthy()
  })
})
