import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../i18n'
import { EN, type StringKey } from '../i18n/en'
import { GateProvider, NOTICE_VERSION } from '../lib/consent'
import { getDeviceId } from '../lib/device'
import { POLL, pollReport } from '../lib/poll'
import { photoToJpeg, TryPhotoError } from '../lib/tryPhoto'
import { TryPhoto } from './TryPhoto'

// The app's fetch, swapped per test: the API, the presigned S3 POST and the poll all go through it.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))
// The poll, watched and run for real. The re-encode is real too, until a test fakes it: a HEIC is refused by it.
vi.mock('../lib/poll', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/poll')>()
  return { ...actual, pollReport: vi.fn(actual.pollReport) }
})
vi.mock('../lib/tryPhoto', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/tryPhoto')>()
  return { ...actual, photoToJpeg: vi.fn(actual.photoToJpeg) }
})

const API = 'https://api.example.test'
const S3 = 'https://uploads.example.test'
const ID = 'r_0123456789abcdef0123456789abcdef'
const UPLOAD = { url: `${S3}/`, fields: { 'Content-Type': 'image/jpeg', key: `raw/${ID}.jpg` } }
const JPEG = new Blob(['jpeg bytes'], { type: 'image/jpeg' })
const DONE = {
  reportId: ID,
  status: 'done',
  mode: 'try',
  published: false,
  capturedAt: '2026-11-02T08:00:00Z',
  noFloodSeen: false,
  level: 'knee',
  landmark: 'rim_three_quarters',
  passability: 'NPLV',
  levelIsFloor: false,
  levelFrom: 'landmark',
  basis: { vehicles: 1, people: 0 },
}
const PENDING = { reportId: ID, status: 'pending', mode: 'try', published: false }

const text = (key: StringKey) => EN[key].text
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
const photo = (type = 'image/jpeg') => new File(['photo bytes'], 'flood', { type })

type Routes = {
  tryRoute?(): Response | Promise<Response>
  s3Route?(): Response | Promise<Response>
  reportRoute?(): Response
}

// A fake of the three places the component talks to. `calls` lists each request, as "POST /try", "POST S3" or
// "GET /reports/<id>", in order.
function mockApi({ tryRoute, s3Route, reportRoute }: Routes = {}) {
  const calls: string[] = []
  const seen: { tryInit?: RequestInit; s3Init?: RequestInit } = {}
  net.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    const method = (init?.method ?? 'GET').toUpperCase()
    if (url.origin === API && method === 'POST' && url.pathname === '/try') {
      calls.push('POST /try')
      seen.tryInit = init
      return tryRoute?.() ?? json(201, { reportId: ID, upload: UPLOAD, expiresInS: 300 })
    }
    if (url.origin === S3 && method === 'POST') {
      calls.push('POST S3')
      seen.s3Init = init
      return s3Route?.() ?? new Response(null, { status: 204 })
    }
    if (url.origin === API && method === 'GET' && url.pathname === `/reports/${ID}`) {
      calls.push(`GET /reports/${ID}`)
      return reportRoute?.() ?? json(200, DONE)
    }
    throw new Error(`Unexpected request: ${method} ${url}`)
  }) as typeof fetch
  return { calls, seen }
}

function renderTry({ consented = true, apiUrl = API }: { consented?: boolean; apiUrl?: string } = {}) {
  if (consented) localStorage.setItem('lusot.consent', JSON.stringify({ adult: true, notice: NOTICE_VERSION }))
  return render(
    <LanguageProvider>
      <GateProvider>
        <TryPhoto apiUrl={apiUrl} />
      </GateProvider>
    </LanguageProvider>,
  )
}

// localStorage that throws on every access, as a blocked site's does.
function blockStorage() {
  vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
    throw new DOMException('The operation is insecure.', 'SecurityError')
  })
}

// Moves the fake clock, with the promises it wakes settled inside act (for the tests that use fake timers).
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}
const fakeClock = () => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] })

const input = () => screen.getByLabelText(text('try.inputLabel')) as HTMLInputElement
const choose = (file = photo()) => fireEvent.change(input(), { target: { files: [file] } })
const button = (key: StringKey) => screen.getByRole('button', { name: text(key) })
const settle = () => act(async () => {})

beforeEach(() => {
  vi.mocked(photoToJpeg).mockReset()
  vi.mocked(pollReport).mockClear()
  net.fetch = vi.fn(() => Promise.reject(new Error('No network in the test'))) as unknown as typeof fetch
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
  localStorage.clear()
  history.replaceState(null, '', '/')
  document.documentElement.removeAttribute('lang')
})

describe('the entry', () => {
  it('has one file input for the three types, labelled, with no capture attribute, and a button that reads "Choose a photo"', () => {
    renderTry()

    expect(input().type).toBe('file')
    expect(input().accept).toBe('image/jpeg,image/png,image/webp')
    expect(input().hasAttribute('capture')).toBe(false)
    expect([...document.querySelectorAll('input')].filter((field) => field.type === 'file')).toHaveLength(1)
    expect(button('try.choose')).toBeTruthy()
  })

  it('the notice gate opens first, and a declined gate opens no picker and sends nothing', () => {
    const { calls } = mockApi()
    const open = vi.spyOn(HTMLInputElement.prototype, 'click')
    renderTry({ consented: false })

    fireEvent.click(button('try.choose'))

    expect(screen.getByRole('heading', { level: 1, name: 'Before your first photo or question' })).toBeTruthy()
    expect(open).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: text('consent.notNow') }))
    expect(open).not.toHaveBeenCalled()
    expect(calls).toEqual([])
    expect(button('try.choose')).toBeTruthy()

    // Accepted, the gate opens the picker: the one file input.
    fireEvent.click(button('try.choose'))
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: text('consent.continue') }))
    expect(open).toHaveBeenCalledTimes(1)
    expect(open.mock.contexts[0]).toBe(input())
    expect(calls).toEqual([])
  })

  it('with the notice passed, the button opens the picker at once', () => {
    const open = vi.spyOn(HTMLInputElement.prototype, 'click')
    renderTry()

    fireEvent.click(button('try.choose'))

    expect(open).toHaveBeenCalledTimes(1)
    expect(open.mock.contexts[0]).toBe(input())
  })

  // A screen reader reaches an input that is in the accessibility tree, and activating it opens the picker with no gate.
  it('keeps the file input out of the accessibility tree and the tab order, so only the gated button opens it', () => {
    renderTry()

    expect(input().getAttribute('aria-hidden')).toBe('true')
    expect(input().tabIndex).toBe(-1)
  })

  it('with no notice accepted, a change event on the input sends nothing', async () => {
    const { calls } = mockApi()
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry({ consented: false })
    let value = 'C:\\fakepath\\flood'
    Object.defineProperty(input(), 'value', {
      configurable: true,
      get: () => value,
      set: (next: string) => {
        value = next
      },
    })

    choose()
    await settle()

    expect(vi.mocked(photoToJpeg)).not.toHaveBeenCalled()
    expect(calls).toEqual([])
    expect(value).toBe('')
    expect(screen.queryByText(text('try.reading'))).toBeNull()
    expect(button('try.choose')).toBeTruthy()
  })

  it('with storage blocked, a photo chosen after passing the gate this visit is still sent', async () => {
    blockStorage()
    const { calls } = mockApi()
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry({ consented: false })
    fireEvent.click(button('try.choose'))
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: text('consent.continue') }))

    choose()

    expect(await screen.findByText(text('result.try'))).toBeTruthy()
    expect(calls.filter((call) => call === 'POST /try')).toHaveLength(1)
  })

  it('with no API address, says so and shows no button and no input', () => {
    renderTry({ apiUrl: '' })

    expect(screen.getByText(text('try.noApi'))).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByLabelText(text('try.inputLabel'))).toBeNull()
  })
})

describe('a chosen photo', () => {
  it('choosing a JPEG posts /try once, uploads it, polls, and shows the try card', async () => {
    const { calls, seen } = mockApi()
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()
    const file = photo()

    choose(file)

    expect(await screen.findByText(text('result.try'))).toBeTruthy()
    expect(vi.mocked(photoToJpeg)).toHaveBeenCalledWith(file)
    expect(calls).toEqual(['POST /try', 'POST S3', `GET /reports/${ID}`])
    // Only the consent version is sent, with the device header.
    expect(seen.tryInit?.body).toBe(JSON.stringify({ consentVersion: NOTICE_VERSION }))
    expect(new Headers(seen.tryInit?.headers).get('x-lusot-device')).toBe(getDeviceId())
    // The re-encoded JPEG goes to S3, after the policy's fields.
    const form = seen.s3Init?.body as FormData
    expect([...form.keys()]).toEqual([...Object.keys(UPLOAD.fields), 'file'])
    expect((form.get('file') as Blob).size).toBe(JPEG.size)
    // The card is the try card: the verdict and level, no photo-taken line, and the button now offers another.
    expect(screen.getByText('Knee deep at this spot (MMDA level).')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/Photo taken|Location within/)
    expect(button('try.chooseAnother')).toBeTruthy()
    expect(screen.queryByRole('button', { name: text('try.choose') })).toBeNull()
  })

  it('shows that Lusot is reading the photo, with no choose button, while the run is under way', async () => {
    mockApi({ reportRoute: () => json(200, PENDING) })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    expect(await screen.findByText(text('try.reading'))).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain(text('try.reading'))
    expect(screen.queryByRole('button', { name: text('try.choose') })).toBeNull()
    expect(screen.queryByRole('button', { name: text('try.chooseAnother') })).toBeNull()
  })

  it('a HEIC file shows try.unsupported and sends nothing', async () => {
    const { calls } = mockApi()
    renderTry()

    choose(photo('image/heic'))

    expect(await screen.findByText(text('try.unsupported'))).toBeTruthy()
    expect(calls).toEqual([])
    expect(button('try.chooseAnother')).toBeTruthy()
  })

  it("a file whose type lies and won't decode shows try.unreadable and sends nothing", async () => {
    const { calls } = mockApi()
    vi.mocked(photoToJpeg).mockRejectedValue(new TryPhotoError('unreadable'))
    renderTry()

    choose(photo('image/jpeg'))

    expect(await screen.findByText(text('try.unreadable'))).toBeTruthy()
    expect(calls).toEqual([])
  })

  it('a canvas or encode failure while preparing the photo shows try.unreadable, not try.sendFailed, and sends nothing', async () => {
    const { calls } = mockApi()
    vi.mocked(photoToJpeg).mockRejectedValue(new Error('Could not encode the photo as JPEG'))
    renderTry()

    choose()

    expect(await screen.findByText(text('try.unreadable'))).toBeTruthy()
    expect(document.body.textContent).not.toContain(text('try.sendFailed'))
    expect(calls).toEqual([])
    expect(button('try.chooseAnother')).toBeTruthy()
  })

  it('a lost connection on the S3 POST is tried once more on the same link, so the photo is paid for once', async () => {
    fakeClock()
    let attempts = 0
    const { calls } = mockApi({
      s3Route: () => {
        attempts += 1
        if (attempts === 1) throw new TypeError('Failed to fetch')
        return new Response(null, { status: 204 })
      },
    })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()
    await advance(0)
    // The retry waits about 2 s (C635).
    await advance(2000)

    expect(screen.getByText(text('result.try'))).toBeTruthy()
    expect(calls.filter((call) => call === 'POST /try')).toHaveLength(1)
    expect(calls.filter((call) => call === 'POST S3')).toHaveLength(2)
    expect(document.body.textContent).not.toContain(text('try.sendFailed'))
  })

  it('a failed card offers no "Try again" of its own: "Choose another photo" below it is the one way on', async () => {
    mockApi({ reportRoute: () => json(200, { reportId: ID, status: 'failed', refusalReason: 'pipeline_error', mode: 'try', published: false }) })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    expect(await screen.findByText('Processing failed, try again.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(button('try.chooseAnother')).toBeTruthy()
  })

  it.each(['model_calls_paused', 'uploads_paused'])(
    'a 503 %s shows the paused notice with the map link, never "Processing failed"',
    async (code) => {
      const { calls } = mockApi({ tryRoute: () => json(503, { error: code }) })
      vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
      renderTry()

      choose()

      expect(await screen.findByText(text('result.paused'))).toBeTruthy()
      expect(screen.getByRole('link', { name: 'Map' }).getAttribute('href')).toBe('#/map')
      expect(screen.queryByRole('link', { name: 'Tested' })).toBeNull()
      expect(document.body.textContent).not.toContain('Processing failed')
      expect(document.body.textContent).not.toContain(text('try.sendFailed'))
      expect(calls).toEqual(['POST /try'])
    },
  )

  it('a poll that ends failed/model_calls_paused shows the card as paused, with the map link only', async () => {
    mockApi({
      reportRoute: () => json(200, { reportId: ID, status: 'failed', refusalReason: 'model_calls_paused', mode: 'try', published: false }),
    })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    expect(await screen.findByText(text('result.paused'))).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Map' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Tested' })).toBeNull()
    expect(document.body.textContent).not.toContain('Processing failed')
  })

  it.each(['device_limit', 'global_cap', 'daily_cap'] as const)('a 429 %s shows try.limit.%s', async (code) => {
    const { calls } = mockApi({ tryRoute: () => json(429, { error: code }) })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    expect(await screen.findByText(text(`try.limit.${code}`))).toBeTruthy()
    expect(calls).toEqual(['POST /try'])
    expect(button('try.chooseAnother')).toBeTruthy()
  })

  it.each([
    ['a 500 from /try', { tryRoute: () => json(500, { error: 'internal' }) }],
    ['a 400 from /try', { tryRoute: () => json(400, { error: 'bad_request' }) }],
    ['an answer with no upload link', { tryRoute: () => json(201, {}) }],
    ['a refused S3 POST', { s3Route: () => new Response('<Error/>', { status: 403 }) }],
  ] as [string, Routes][])('%s shows try.sendFailed', async (_name, routes) => {
    mockApi(routes)
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    expect(await screen.findByText(text('try.sendFailed'))).toBeTruthy()
    expect(document.body.textContent).not.toContain('Processing failed')
    expect(pollReport).not.toHaveBeenCalled()
    expect(button('try.chooseAnother')).toBeTruthy()
  })

  it('a lost connection on /try shows try.sendFailed', async () => {
    net.fetch = vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))) as unknown as typeof fetch
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    expect(await screen.findByText(text('try.sendFailed'))).toBeTruthy()
  })
})

// The section is wide from lg, so the component's own lines (what it is doing, why it refused, that the notice is paused)
// keep to a line of 65 characters, as the Tested page's text does. The result card keeps the section's whole width.
describe('from lg', () => {
  const PROSE = 'lg:max-w-prose'
  const capped = (element: Element | null) => element?.classList.contains(PROSE) === true

  it('keeps to a line of 65 characters with no API address', () => {
    renderTry({ apiUrl: '' })

    expect(capped(screen.getByText(text('try.noApi')))).toBe(true)
  })

  it('keeps to a line of 65 characters while Lusot reads the photo', async () => {
    mockApi({ reportRoute: () => json(200, PENDING) })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    expect(capped((await screen.findByText(text('try.reading'))).closest('p'))).toBe(true)
  })

  it.each([
    ['a file problem', {}, 'image/heic', 'try.unsupported'],
    ['a limit', { tryRoute: () => json(429, { error: 'device_limit' }) }, 'image/jpeg', 'try.limit.device_limit'],
    ['a failed send', { tryRoute: () => json(500, { error: 'internal' }) }, 'image/jpeg', 'try.sendFailed'],
  ] as [string, Routes, string, StringKey][])('keeps %s to a line of 65 characters', async (_name, routes, type, key) => {
    mockApi(routes)
    // A HEIC is refused by the real re-encode, so only a JPEG is faked.
    if (type === 'image/jpeg') vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose(photo(type))

    expect(capped(await screen.findByText(text(key)))).toBe(true)
  })

  it('keeps the paused line (a 503 from /try) to a line of 65 characters', async () => {
    mockApi({ tryRoute: () => json(503, { error: 'uploads_paused' }) })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    expect(capped((await screen.findByText(text('result.paused'))).closest('.mt-3'))).toBe(true)
  })

  it("leaves the result card the section's whole width", async () => {
    mockApi()
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()

    await screen.findByText(text('result.try'))
    expect(capped(screen.getByRole('article').closest('.mt-3'))).toBe(false)
  })
})

describe('one run at a time', () => {
  it('two change events in one tick start one run', async () => {
    const { calls } = mockApi()
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()
    const file = photo()

    act(() => {
      choose(file)
      choose(file)
    })

    expect(await screen.findByText(text('result.try'))).toBeTruthy()
    expect(calls.filter((call) => call === 'POST /try')).toHaveLength(1)
    expect(vi.mocked(photoToJpeg)).toHaveBeenCalledTimes(1)
  })

  it('a second choice while a run is in flight starts nothing', async () => {
    const { calls } = mockApi({ reportRoute: () => json(200, PENDING) })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()
    await screen.findByText(text('try.reading'))
    choose(photo('image/png'))
    await settle()

    expect(calls.filter((call) => call === 'POST /try')).toHaveLength(1)
    expect(vi.mocked(photoToJpeg)).toHaveBeenCalledTimes(1)
  })

  it("clears the input's value after a choice, so the same file can be chosen again", async () => {
    mockApi()
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()
    // A browser's file input keeps the chosen file's name as its value until a script clears it.
    let value = 'C:\\fakepath\\flood'
    Object.defineProperty(input(), 'value', {
      configurable: true,
      get: () => value,
      set: (next: string) => {
        value = next
      },
    })

    choose()

    expect(value).toBe('')
    await screen.findByText(text('result.try'))
  })

  it('choosing the same file again after a result runs it again', async () => {
    const { calls } = mockApi()
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()
    const file = photo()

    choose(file)
    await screen.findByText(text('result.try'))
    choose(file)
    await waitFor(() => expect(calls.filter((call) => call === 'POST /try')).toHaveLength(2))

    expect(await screen.findByText(text('result.try'))).toBeTruthy()
    expect(vi.mocked(photoToJpeg)).toHaveBeenCalledTimes(2)
  })
})

describe('the wait', () => {
  it('unmounting mid-poll aborts the poll, and nothing updates after it', async () => {
    const { calls } = mockApi({ reportRoute: () => json(200, PENDING) })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    const errors = vi.spyOn(console, 'error')
    const { unmount } = renderTry()

    choose()
    await screen.findByText(text('try.reading'))
    const signal = vi.mocked(pollReport).mock.calls[0][2]?.signal
    expect(signal?.aborted).toBe(false)

    unmount()
    await settle()

    expect(signal?.aborted).toBe(true)
    const reads = calls.length
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(calls).toHaveLength(reads)
    expect(errors).not.toHaveBeenCalled()
  })

  it('a poll past its deadline says "No result yet", and "Check again" polls the same report again', async () => {
    fakeClock()
    const { calls } = mockApi({ reportRoute: () => json(200, PENDING) })
    vi.mocked(photoToJpeg).mockResolvedValue(JPEG)
    renderTry()

    choose()
    await advance(0)
    expect(screen.getByText(text('try.reading'))).toBeTruthy()
    await advance(POLL.windowMs)

    expect(screen.getByText(text('result.noResult'))).toBeTruthy()
    expect(document.body.textContent).not.toContain('Processing failed')
    expect(calls.filter((call) => call === 'POST /try')).toHaveLength(1)
    const checkedAt = Date.now()
    fireEvent.click(screen.getByRole('button', { name: text('result.checkAgain') }))
    await advance(0)

    expect(calls.filter((call) => call === 'POST /try')).toHaveLength(1)
    expect(vi.mocked(pollReport)).toHaveBeenCalledTimes(2)
    const [, againId, options] = vi.mocked(pollReport).mock.calls[1]
    expect(againId).toBe(ID)
    expect(options?.startElapsedMs).toBe(POLL.midForMs)
    expect(options?.deadlineAt).toBe(checkedAt + POLL.windowMs)
    expect(screen.getByText(text('try.reading'))).toBeTruthy()
  })
})

describe('the primary button carries an icon, hidden from screen readers, and keeps its words', () => {
  it('"Choose a photo" has one', () => {
    mockApi()
    renderTry()
    expect(button('try.choose').querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
    expect(button('try.choose').textContent).toBe(text('try.choose'))
  })
})
