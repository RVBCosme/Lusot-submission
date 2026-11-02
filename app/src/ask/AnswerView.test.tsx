import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { LanguageProvider } from '../i18n'
import type { AskAnswer, AskReport } from '../lib/api'
import { AnswerView } from './AnswerView'

// A demo card's credit line can hold a licence URL, which has no space to break at. It may break anywhere, so on a phone it
// wraps inside the card and never widens /#/ask (Rene's device check, Nov 2; e2e/overflow.spec.ts measures it). Only the
// credit line gets that rule: the photographer's own words, which Lusot can't rewrap or reword.
const URL_CREDIT = 'Photo: Example Contributor (mock), CC BY 3.0 (https://creativecommons.org/licenses/by/3.0)'
const NOW = new Date('2026-10-30T10:30:00Z')

const DEMO: AskReport = {
  id: 'r_00000000000000000000000000000001',
  lat: 14.6342,
  lng: 121.0965,
  capturedAt: '2009-09-26T01:30:00Z',
  mode: 'demo',
  flags: 0,
  gpsAccuracyM: null,
  level: 'above_chest',
  landmark: 'rim_three_quarters',
  passability: 'NPATV',
  levelIsFloor: false,
  basis: { vehicles: 1, people: 0 },
  distanceM: 210,
  credit: URL_CREDIT,
  place: 'Marikina',
  event: 'Typhoon Ondoy',
}

const ANSWER: AskAnswer = {
  source: 'model',
  fallback: null,
  kind: 'reports',
  crossing: false,
  vehicle: null,
  place: { name: 'España Blvd cor. Maceda St', source: 'spots' },
  windowMin: 180,
  radiusM: 300,
  count: 0,
  reports: [],
  demo: [DEMO],
  deepestId: null,
  cited: [],
  suggestions: [],
}

afterEach(cleanup)

describe('a demo card in an answer', () => {
  it('lets its credit line break anywhere, and no other line of the card', () => {
    render(
      <LanguageProvider>
        <AnswerView answer={ANSWER} now={NOW} onSuggestion={() => {}} />
      </LanguageProvider>,
    )
    const credit = screen.getByText(URL_CREDIT)
    expect(credit.hasAttribute('data-line')).toBe(true)
    expect(credit.className).toContain('wrap-anywhere')

    const card = credit.closest('a') as HTMLElement
    const others = [...card.querySelectorAll<HTMLElement>('[data-line]')].filter((line) => line !== credit)
    expect(others.length).toBeGreaterThan(1)
    for (const line of others) expect(line.className, line.textContent ?? '').not.toContain('wrap-anywhere')
  })
})
