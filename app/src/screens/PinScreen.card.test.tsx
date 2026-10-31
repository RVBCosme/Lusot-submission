import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ResultCardProps } from '../components/ResultCard'
import { LanguageProvider } from '../i18n'
import { createMockFetch } from '../mock/mockFetch'
import { PinScreen } from './PinScreen'

// Pin detail hands the card the GET /reports/{id} answer, with its links, so the card's captions and Task 14's overlay
// see them. The card is replaced here by a recorder of what it was given.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch, cards: [] as unknown[] }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))
vi.mock('../report/ReportFlowProvider', () => ({ useOwnPin: () => undefined, useSeenOnMap: () => () => {} }))
vi.mock('../components/ResultCard', () => ({
  ResultCard: (props: unknown) => {
    net.cards.push(props)
    return <article data-testid="card" />
  },
}))

const API = 'https://api.example.test'
const B = 'r_2b3c4d5e6f7a41829304b5c6d7e8f9a0'
const E = 'r_5e6f7a8b9c0d44b506c7d8e9f0a1b2c3'

afterEach(() => {
  cleanup()
  net.cards = []
})

async function cardFor(id: string): Promise<ResultCardProps> {
  net.fetch = createMockFetch({ now: () => Date.now() })
  render(
    <LanguageProvider>
      <main>
        <PinScreen apiUrl={API} id={id} />
      </main>
    </LanguageProvider>,
  )
  await screen.findByTestId('card')
  return net.cards.at(-1) as ResultCardProps
}

describe('what pin detail gives the card', () => {
  it('is the report with its photo, overlay and layers links, as a pin card, and a way to ask for a new link', async () => {
    const props = await cardFor(B)
    const result = props.result as { photoUrl?: string; overlayUrl?: string; layersUrl?: string; status?: string }
    expect(props.source).toBe('pin')
    expect(result.status).toBe('done')
    expect(result.photoUrl).toMatch(/^data:image/)
    expect(result.overlayUrl).toMatch(/^data:image/)
    expect(result.layersUrl).toBe(`https://mock-files.invalid/layers/${B}.json`)
    expect(typeof props.onPhotoExpired).toBe('function')
    expect(props.now).toBeInstanceOf(Date)
  })

  it("keeps a demo pin's credit, place and event on the result, from the pin or the report", async () => {
    const props = await cardFor(E)
    expect(props.result).toMatchObject({
      mode: 'demo',
      credit: 'Photo: Example Contributor (mock), CC BY 4.0, faces and plates blurred by Lusot',
      place: 'Marikina',
      event: 'Typhoon Ondoy',
    })
    expect((props.result as { overlayUrl?: string }).overlayUrl).toBeDefined()
  })
})
