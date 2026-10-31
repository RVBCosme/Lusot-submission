import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest'
import { LanguageProvider } from '../i18n'
import { EN, type StringKey } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { writeItem } from '../lib/storage'
import source from './LicencesScreen.tsx?raw'
import { LicencesScreen } from './LicencesScreen'

const TEXT = ['leaflet 1.9.4', 'License: BSD-2-Clause', '', 'Redistribution and use in source and binary forms.'].join('\n')

const NEW_KEYS: StringKey[] = [
  'licences.intro',
  'licences.loading',
  'licences.unavailable',
  'licences.textLabel',
  'licences.otherTitle',
  'licences.osm',
  'licences.osmLink',
  'licences.samples',
  'licences.packagesTitle',
  'licences.packagesNote',
]

const text = (key: StringKey) => EN[key].text

let fetchSpy: MockInstance<typeof fetch>

function answer(body: string, init: ResponseInit = {}) {
  fetchSpy.mockResolvedValue(new Response(body, { status: 200, headers: { 'content-type': 'text/plain' }, ...init }))
}

function renderPage() {
  return render(
    <LanguageProvider>
      <LicencesScreen />
    </LanguageProvider>,
  )
}

beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, 'fetch')
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.removeAttribute('lang')
})

describe('the licence texts', () => {
  it('shows the text the build wrote as preformatted text in a labelled, focusable, scrolling region', async () => {
    answer(TEXT)
    renderPage()

    const region = await screen.findByRole('region', { name: text('licences.textLabel') })
    const pre = region.querySelector('pre')
    expect(pre?.textContent).toBe(TEXT)
    expect(region.getAttribute('tabindex')).toBe('0')
    expect(region.className).toMatch(/overflow-(y-)?auto/)
  })

  it('asks for ./licences.txt once, plainly, and never through the API client', async () => {
    answer(TEXT)
    renderPage()
    await screen.findByRole('region', { name: text('licences.textLabel') })

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy.mock.calls[0][0]).toBe('./licences.txt')
    expect(source).not.toContain('apiFetch')
    expect(source).not.toMatch(/lib\/api/)
  })

  it('says it is loading while the file is on its way, with no text yet', () => {
    fetchSpy.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByText(text('licences.loading'))).toBeTruthy()
    expect(screen.queryByRole('region', { name: text('licences.textLabel') })).toBeNull()
  })

  it.each([
    ['the network fails', () => fetchSpy.mockRejectedValue(new TypeError('offline'))],
    ['the file is missing', () => answer('Not found', { status: 404 })],
    ['the server answers with a page instead of the file', () => answer('<!doctype html><html></html>', { headers: { 'content-type': 'text/html' } })],
    ['the file is empty', () => answer('')],
  ])('says in one plain line that it could not load when %s', async (_name, arrange) => {
    arrange()
    renderPage()

    expect(await screen.findByText(text('licences.unavailable'))).toBeTruthy()
    expect(screen.queryByText(text('licences.loading'))).toBeNull()
    expect(screen.queryByRole('region', { name: text('licences.textLabel') })).toBeNull()
    expect(document.body.innerHTML).not.toContain('<!doctype')
  })
})

describe('the page', () => {
  it('the heading takes focus when the page opens', () => {
    answer(TEXT)
    renderPage()

    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1 }))
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(text('licences.title'))
  })

  it('names the sources that are not packages: OpenStreetMap, linked, and the sample photos credits', async () => {
    answer(TEXT)
    renderPage()
    await screen.findByRole('region', { name: text('licences.textLabel') })

    expect(screen.getByRole('heading', { level: 2, name: text('licences.otherTitle') })).toBeTruthy()
    expect(screen.getByText(text('licences.osm'), { exact: false })).toBeTruthy()
    const link = screen.getByRole('link', { name: text('licences.osmLink') })
    expect(link.getAttribute('href')).toBe('https://www.openstreetmap.org/copyright')
    expect(screen.getByText(text('licences.samples'))).toBeTruthy()
    expect(document.body.textContent).toContain('OpenStreetMap contributors')
  })

  it('heads the package list with what it covers, the Android app and type-only packages included', async () => {
    answer(TEXT)
    renderPage()
    const region = await screen.findByRole('region', { name: text('licences.textLabel') })

    const heading = screen.getByRole('heading', { level: 2, name: text('licences.packagesTitle') })
    const note = screen.getByText(text('licences.packagesNote'))
    expect(heading.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(note.compareDocumentPosition(region) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(text('licences.packagesNote')).toMatch(/Android/)
    expect(text('licences.packagesNote')).toMatch(/type/)
  })

  it('shows that heading while the file is loading, and if it fails', async () => {
    fetchSpy.mockRejectedValue(new TypeError('offline'))
    renderPage()
    await screen.findByText(text('licences.unavailable'))

    expect(screen.getByRole('heading', { level: 2, name: text('licences.packagesTitle') })).toBeTruthy()
  })

  it('in Taglish, its own lines are Taglish, and the licence text stays English and is marked so', async () => {
    writeItem('lusot.lang', 'fil')
    answer(TEXT)
    renderPage()
    const region = await screen.findByRole('region', { name: FIL['licences.textLabel'].text })

    expect(screen.getByText(FIL['licences.intro'].text)).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(FIL['licences.title'].text)
    const pre = region.querySelector('pre')
    expect(pre?.textContent).toBe(TEXT)
    expect(pre?.getAttribute('lang')).toBe('en')
  })

  it('has its lines in both languages, each reviewed by Rene (Oct 31)', () => {
    for (const key of NEW_KEYS) {
      expect(EN[key].reviewed, `en ${key}`).toBe(true)
      expect(FIL[key].reviewed, `fil ${key}`).toBe(true)
      expect(EN[key].text, `en ${key}`).not.toBe('')
      expect(FIL[key].text, `fil ${key}`).not.toBe('')
    }
  })

  it("credits OpenStreetMap as its copyright page does: the data under the ODbL, the tiles under the Tile Usage Policy", () => {
    // Checked against openstreetmap.org/copyright and the OSMF attribution guidelines on Oct 31: the ODbL covers the
    // data, and neither page gives the tiles a licence.
    expect(EN['licences.osm'].text).toBe(
      'Map data © OpenStreetMap contributors, under the Open Database License (ODbL). The map tiles come from ' +
        'OpenStreetMap, under its Tile Usage Policy.',
    )
    expect(FIL['licences.osm'].text).toBe(
      'Ang map data ay © OpenStreetMap contributors, sa ilalim ng Open Database License (ODbL). Ang mga map tile ay ' +
        'mula sa OpenStreetMap, ayon sa Tile Usage Policy nito.',
    )
  })
})
