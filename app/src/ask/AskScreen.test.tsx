import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LanguageProvider } from '../i18n'
import { EN, type StringKey } from '../i18n/en'
import { GateProvider, NOTICE_VERSION } from '../lib/consent'
import { LocationDenied, PoorFix, waitForFix } from '../lib/geo'
import { writeItem } from '../lib/storage'
import { ASK_TRANSCRIPT } from '../mock/fixtures'
import { createMockFetch } from '../mock/mockFetch'
import { AskScreen } from './AskScreen'
import { MicDenied, MicUnavailable, RecordingCancelled, startRecording, type Recording, type RecordingOptions } from './recorder'

// The app's fetch, swapped per test for Task 6's mock API (which answers Ask by a word in the question), wrapped so a
// test can count, hold or replace the calls.
const net = vi.hoisted(() => ({ fetch: undefined as unknown as typeof fetch }))
vi.mock('../lib/apiFetch', () => ({
  apiFetch: (input: RequestInfo | URL, init?: RequestInit) => net.fetch(input, init),
}))
vi.mock('../lib/geo', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/geo')>()
  return { ...actual, waitForFix: vi.fn() }
})
vi.mock('./recorder', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./recorder')>()
  return { ...actual, startRecording: vi.fn() }
})

const API = 'https://api.example.test'
const text = (key: StringKey, vars: Record<string, string | number> = {}) =>
  EN[key].text.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name]))
const BANNED_WORDS = /safe|ligtas/i

type Call = { path: string; body: Record<string, unknown> }
let calls: Call[]
let mock: typeof fetch

function useMock(answer: (path: string, body: Record<string, unknown>) => Response | undefined | Promise<Response | undefined> = () => undefined) {
  calls = []
  mock = createMockFetch()
  net.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname
    const body = JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>
    calls.push({ path, body })
    return (await answer(path, body)) ?? mock(input, init)
  }) as typeof fetch
}

function renderAsk({ consented = true, apiUrl = API }: { consented?: boolean; apiUrl?: string } = {}) {
  if (consented) writeItem('lusot.consent', JSON.stringify({ adult: true, notice: NOTICE_VERSION }))
  return render(
    <LanguageProvider>
      <GateProvider>
        <AskScreen apiUrl={apiUrl} />
      </GateProvider>
    </LanguageProvider>,
  )
}

const box = () => screen.getByRole('textbox', { name: text('ask.ui.questionLabel') })
const askButton = () => screen.getByRole('button', { name: text('ask.ui.send') })
const micButton = () => screen.getByRole('button', { name: text('ask.ui.mic') })

async function askTyped(question: string) {
  fireEvent.change(box(), { target: { value: question } })
  fireEvent.click(askButton())
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

// A recording the test finishes: stop() gives a short clip, unless the test makes it reject.
function fakeRecording(stop: () => Promise<Uint8Array> = async () => new Uint8Array(44 + 16000)) {
  const recording: Recording = { stop: vi.fn(stop), cancel: vi.fn() }
  vi.mocked(startRecording).mockResolvedValue(recording)
  return recording
}

// The options the screen gave the recorder, so a test can play its part: a tick, or a cancel of its own.
const recorderOptions = (): RecordingOptions => vi.mocked(startRecording).mock.calls[0][0]

// A location that never answers on its own: it rejects only when its signal aborts, with the signal's reason.
const pendingFix = () =>
  vi.mocked(waitForFix).mockImplementation(
    ({ signal } = {}) => new Promise((_, reject) => signal?.addEventListener('abort', () => reject(signal.reason))),
  )

beforeEach(() => {
  useMock()
  vi.mocked(waitForFix).mockReset()
  vi.mocked(startRecording).mockReset()
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  localStorage.clear()
})

describe('AskScreen', () => {
  it('the gate opens before the first question', async () => {
    renderAsk({ consented: false })

    await askTyped('Gaano kalalim ang baha sa España cor. Maceda?')

    expect(await screen.findByRole('checkbox', { name: new RegExp(text('consent.adult').replace('.', '\\.')) })).toBeTruthy()
    expect(calls).toEqual([])
    fireEvent.click(screen.getByRole('checkbox', { name: new RegExp(text('consent.adult').replace('.', '\\.')) }))
    fireEvent.click(screen.getByRole('button', { name: text('consent.continue') }))

    expect(await screen.findByText(/3 reports within 300 m of España Blvd cor\. Maceda St/)).toBeTruthy()
    expect(calls.map((call) => call.path)).toEqual(['/ask'])
  })

  it('a second send waits for the first', async () => {
    let release: () => void = () => {}
    const held = new Promise<void>((resolve) => (release = resolve))
    useMock(async () => {
      await held
      return undefined
    })
    renderAsk()

    await askTyped('Baha ba sa Marikina?')
    fireEvent.click(askButton())
    fireEvent.submit(box().closest('form') as HTMLFormElement)

    expect(calls).toHaveLength(1)
    // Waiting, but still focusable, so the focus a tap put on it stays there.
    expect(askButton().getAttribute('aria-disabled')).toBe('true')
    expect((askButton() as HTMLButtonElement).disabled).toBe(false)
    expect(box().hasAttribute('readonly')).toBe(true)
    expect(screen.getByText(text('ask.ui.asking'))).toBeTruthy()
    await act(async () => release())
    expect(await screen.findByText(/No recent reports within 300 m of Marikina Riverbanks/)).toBeTruthy()

    // The next question clears the first answer at once, so it never shows under the second question.
    let releaseSecond: () => void = () => {}
    const heldSecond = new Promise<void>((resolve) => (releaseSecond = resolve))
    useMock(async () => {
      await heldSecond
      return undefined
    })
    await askTyped('Ano ang ulam mamaya?')
    expect(screen.queryByText(/No recent reports within 300 m of Marikina Riverbanks/)).toBeNull()
    await act(async () => releaseSecond())
    expect(await screen.findByText(text('ask.answer.offTopic'))).toBeTruthy()
  })

  it('the box stops at 300 characters', () => {
    renderAsk()

    fireEvent.change(box(), { target: { value: 'a'.repeat(301) } })

    expect((box() as HTMLInputElement).value).toHaveLength(300)
    expect(box().getAttribute('maxlength')).toBe('300')
  })

  it('an empty or blank question sends nothing', () => {
    renderAsk()

    fireEvent.change(box(), { target: { value: '   ' } })
    fireEvent.click(askButton())

    expect(calls).toEqual([])
  })

  it('a poor fix is never sent', async () => {
    vi.mocked(waitForFix).mockRejectedValue(new PoorFix(250))
    renderAsk()

    fireEvent.click(screen.getByRole('switch', { name: text('ask.ui.location') }))
    expect(await screen.findByText(text('ask.ui.locationPoor'))).toBeTruthy()
    expect(vi.mocked(waitForFix).mock.calls[0][0]).toMatchObject({ maxWaitMs: 10_000, goodM: 100 })
    await askTyped('May baha ba dito?')

    expect(await screen.findByText(text('ask.answer.noLocation'))).toBeTruthy()
    expect(calls.map((call) => call.body)).toEqual([{ question: 'May baha ba dito?' }])
  })

  it('a good fix is sent with the question, and the location is asked again for each one', async () => {
    vi.mocked(waitForFix).mockResolvedValue({ lat: 14.6095, lng: 120.9894, accuracyM: 20 })
    renderAsk()

    fireEvent.click(screen.getByRole('switch', { name: text('ask.ui.location') }))
    await askTyped('May baha ba dito?')
    expect(await screen.findByText(/3 reports within 300 m of you/)).toBeTruthy()
    await askTyped('May baha ba dito ngayon?')
    await waitFor(() => expect(calls).toHaveLength(2))

    const here = { lat: 14.6095, lng: 120.9894, accuracyM: 20 }
    expect(calls.map((call) => call.body.here)).toEqual([here, here])
    // The switch's own fix, then one for each question.
    expect(waitForFix).toHaveBeenCalledTimes(3)
  })

  it('leaving the screen while the location is found sends nothing', async () => {
    pendingFix()
    const { unmount } = renderAsk()

    fireEvent.click(screen.getByRole('switch', { name: text('ask.ui.location') }))
    await askTyped('May baha ba dito?')
    unmount()
    await act(async () => {})

    expect(calls).toEqual([])
  })

  it('switching the location off drops the fix it was finding', async () => {
    vi.useFakeTimers()
    pendingFix()
    renderAsk()
    const toggle = screen.getByRole('switch', { name: text('ask.ui.location') })

    fireEvent.click(toggle)
    const signal = vi.mocked(waitForFix).mock.calls[0][0]?.signal
    fireEvent.click(toggle)
    await act(async () => vi.advanceTimersByTime(10_000))

    expect(signal?.aborted).toBe(true)
    expect(screen.queryByText(text('ask.ui.locationPoor'))).toBeNull()
    expect(screen.queryByText(text('ask.ui.locationWaiting'))).toBeNull()
  })

  it('a turned-off location, or a timed-out one, gets Ask\'s own line, in a live region', async () => {
    vi.mocked(waitForFix).mockRejectedValue(new LocationDenied('OS-PLUG-GLOC-0009'))
    renderAsk()

    fireEvent.click(screen.getByRole('switch', { name: text('ask.ui.location') }))

    const line = await screen.findByText(text('ask.ui.locationTurnOn'))
    expect(line.closest('[aria-live="polite"]')).not.toBeNull()
    cleanup()
    vi.mocked(waitForFix).mockRejectedValue(new LocationDenied('OS-PLUG-GLOC-0010'))
    renderAsk()
    fireEvent.click(screen.getByRole('switch', { name: text('ask.ui.location') }))
    expect(await screen.findByText(text('ask.ui.locationPoor'))).toBeTruthy()
  })

  it('the wait for a fix ends after 10 s, however the location answers', async () => {
    vi.useFakeTimers()
    pendingFix()
    renderAsk()

    fireEvent.click(screen.getByRole('switch', { name: text('ask.ui.location') }))
    expect(screen.getByText(text('ask.ui.locationWaiting'))).toBeTruthy()
    await act(async () => vi.advanceTimersByTime(10_000))

    expect(screen.getByText(text('ask.ui.locationPoor'))).toBeTruthy()
  })

  it('a refused location says why, with MS5\'s line', async () => {
    vi.mocked(waitForFix).mockRejectedValue(new LocationDenied('PERMISSION_DENIED'))
    renderAsk()

    fireEvent.click(screen.getByRole('switch', { name: text('ask.ui.location') }))

    expect(await screen.findByText(text('location.denied'))).toBeTruthy()
  })

  it.each([
    ['Show the limit', 'ask.error.questionLimit'],
    ['Show the cap', 'ask.error.questionCap'],
    ['Ask unavailable?', 'ask.error.unavailable'],
  ] as const)('"%s" shows %s, and isn\'t retried', async (question, key) => {
    renderAsk()

    await askTyped(question)

    const pattern = new RegExp(EN[key].text.replace(/[.?]/g, '\\$&').replace(/\{min\}/, '\\d+'))
    expect(await screen.findByText(pattern)).toBeTruthy()
    expect(calls).toHaveLength(1)
  })

  it.each([
    [503, 'voice_paused', 'ask.error.voicePaused'],
    // A failed or late transcription is a passing fault, not a clip that went unheard (Nov 3).
    [503, 'voice_failed', 'ask.error.unavailable'],
    [422, 'audio_too_short', 'ask.error.voiceFailed'],
    [422, 'audio_too_long', 'ask.error.voiceFailed'],
    [400, 'bad_audio', 'ask.error.voiceFailed'],
    [503, 'ask_unavailable', 'ask.error.unavailable'],
  ] as const)('a spoken %i %s shows its line, and isn\'t retried', async (status, code, key) => {
    useMock((path) => (path === '/ask/voice' ? json(status, { error: code }) : undefined))
    fakeRecording()
    renderAsk()

    fireEvent.click(micButton())
    fireEvent.click(await screen.findByRole('button', { name: text('ask.ui.micStop') }))

    expect(await screen.findByText(text(key))).toBeTruthy()
    expect(calls).toHaveLength(1)
  })

  it.each([
    [new MicDenied(), 'ask.error.micDenied'],
    [new MicUnavailable(), 'ask.error.micUnavailable'],
  ] as const)('a microphone that fails with %s offers typing instead', async (err, key) => {
    vi.mocked(startRecording).mockRejectedValue(err)
    renderAsk()

    fireEvent.click(micButton())

    expect(await screen.findByText(text(key))).toBeTruthy()
    expect(calls).toEqual([])
  })

  it('the mic keeps the focus: one button turns into Stop, and back', async () => {
    fakeRecording()
    renderAsk()
    const mic = micButton()
    mic.focus()

    fireEvent.click(mic)
    const stop = await screen.findByRole('button', { name: text('ask.ui.micStop') })

    expect(stop).toBe(mic)
    expect(document.activeElement).toBe(mic)
    fireEvent.click(stop)
    await screen.findByText(text('ask.ui.youAsked'))
    expect(screen.getByRole('button', { name: text('ask.ui.mic') })).toBe(mic)
    expect(document.activeElement).toBe(mic)
  })

  it('the recording sends itself at 14.9 s', async () => {
    fakeRecording()
    renderAsk()

    fireEvent.click(micButton())
    await screen.findByRole('button', { name: text('ask.ui.micStop') })
    expect(recorderOptions().maxMs).toBe(14_900)
    await act(async () => recorderOptions().onTick(0))

    expect(await screen.findByText(text('ask.ui.youAsked'))).toBeTruthy()
    expect(calls.map((call) => call.path)).toEqual(['/ask/voice'])
  })

  it('the countdown follows the recorder\'s ticks', async () => {
    fakeRecording()
    renderAsk()

    fireEvent.click(micButton())
    await screen.findByRole('button', { name: text('ask.ui.micStop') })
    await act(async () => recorderOptions().onTick(9_400))

    expect(screen.getByRole('timer').textContent).toBe(text('ask.ui.micLeft', { s: 10 }))
  })

  it('a spoken answer shows "You asked:" and the transcript', async () => {
    const recording = fakeRecording()
    renderAsk()

    fireEvent.click(micButton())
    const stop = await screen.findByRole('button', { name: text('ask.ui.micStop') })
    expect(screen.getByText(text('ask.ui.micLeft', { s: 15 }))).toBeTruthy()
    fireEvent.click(stop)

    expect(await screen.findByText(text('ask.ui.youAsked'))).toBeTruthy()
    const answer = screen.getByRole('region', { name: text('ask.ui.answer') })
    expect(within(answer).getByText(ASK_TRANSCRIPT)).toBeTruthy()
    expect(screen.getByText(/3 reports within 300 m of España Blvd cor\. Maceda St/)).toBeTruthy()
    expect(recording.stop).toHaveBeenCalledOnce()
    expect(calls.map((call) => call.path)).toEqual(['/ask/voice'])
    expect(typeof calls[0].body.audio).toBe('string')
  })

  it("a transcript's banned words are masked", async () => {
    const answer = await (await mock(`${API}/ask`, { method: 'POST', body: JSON.stringify({ question: 'España cor. Maceda' }) })).json()
    useMock((path) => (path === '/ask/voice' ? json(200, { ...answer, transcript: 'Ligtas ba sa España cor. Maceda?' }) : undefined))
    fakeRecording()
    renderAsk()

    fireEvent.click(micButton())
    fireEvent.click(await screen.findByRole('button', { name: text('ask.ui.micStop') }))

    expect(await screen.findByText('•••••• ba sa España cor. Maceda?')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(BANNED_WORDS)
  })

  it('a recording cancelled by the page going hidden sends nothing, and the screen is ready again', async () => {
    fakeRecording()
    renderAsk()

    fireEvent.click(micButton())
    await screen.findByRole('button', { name: text('ask.ui.micStop') })
    await act(async () => recorderOptions().onCancel?.())

    expect(screen.getByRole('button', { name: text('ask.ui.mic') })).toBeTruthy()
    expect(askButton().getAttribute('aria-disabled')).toBe('false')
    expect(calls).toEqual([])
  })

  it('a stop after the recording was cancelled sends nothing', async () => {
    fakeRecording(async () => {
      throw new RecordingCancelled()
    })
    renderAsk()

    fireEvent.click(micButton())
    fireEvent.click(await screen.findByRole('button', { name: text('ask.ui.micStop') }))

    expect(await screen.findByRole('button', { name: text('ask.ui.mic') })).toBeTruthy()
    expect(calls).toEqual([])
  })

  it('an answer that comes after the screen closed is dropped', async () => {
    let release: () => void = () => {}
    const held = new Promise<void>((resolve) => (release = resolve))
    useMock(async () => {
      await held
      return undefined
    })
    const { unmount } = renderAsk()

    await askTyped('Baha ba sa España cor. Maceda?')
    unmount()
    await act(async () => release())

    expect(calls).toHaveLength(1)
    expect(document.body.textContent).toBe('')
  })

  it('leaving the screen mid-recording cancels the recording', async () => {
    const recording = fakeRecording()
    const { unmount } = renderAsk()

    fireEvent.click(micButton())
    await screen.findByRole('button', { name: text('ask.ui.micStop') })
    unmount()

    expect(recording.cancel).toHaveBeenCalledOnce()
    expect(vi.mocked(startRecording).mock.calls[0][0].signal?.aborted).toBe(true)
    expect(calls).toEqual([])
  })

  it('cards link to their pins', async () => {
    renderAsk()

    await askTyped('Baha ba sa España cor. Maceda?')
    const answer = await screen.findByRole('region', { name: text('ask.ui.answer') })

    const hrefs = within(answer).getAllByRole('link').map((link) => link.getAttribute('href'))
    expect(hrefs.length).toBeGreaterThan(1)
    for (const href of hrefs) expect(href).toMatch(/^#\/pin\/r_[0-9a-f]{32}$/)
    expect(within(answer).getAllByText(text('ask.ui.used')).length).toBeGreaterThan(0)
    expect(within(answer).getByText(text('ask.answer.demo'))).toBeTruthy()
  })

  it('the attribution shows only for a Nominatim place', async () => {
    renderAsk()

    await askTyped('Baha ba malapit sa Quiapo Church?')
    expect(await screen.findByText(text('ask.ui.attribution'))).toBeTruthy()

    await askTyped('Baha ba sa España cor. Maceda?')
    await screen.findByText(/within 300 m of España Blvd cor\. Maceda St/)
    expect(screen.queryByText(text('ask.ui.attribution'))).toBeNull()
  })

  it('the notice line is always visible, linked to the privacy policy', async () => {
    renderAsk()
    const notice = () => screen.getByText(text('ask.ui.notice'))
    expect(notice().closest('a')?.getAttribute('href')).toBe('#/privacy')

    await askTyped('Baha ba sa España cor. Maceda?')
    await screen.findByText(/within 300 m of España Blvd cor\. Maceda St/)

    expect(notice()).toBeTruthy()
  })

  it('a suggestion and an example fill the box, and send nothing', async () => {
    renderAsk()

    fireEvent.click(screen.getByRole('button', { name: text('ask.ui.example2') }))
    expect((box() as HTMLInputElement).value).toBe(text('ask.ui.example2'))

    await askTyped('Gaano kalalim sa Taft Avenue?')
    const suggestion = await screen.findByRole('button', { name: text('ask.ui.suggestionQuestion', { spot: 'Taft Ave in front of PGH' }) })
    fireEvent.click(suggestion)

    expect((box() as HTMLInputElement).value).toBe('How deep is it at Taft Ave in front of PGH?')
    expect(calls).toHaveLength(1)
  })

  it('without an API address, it says so and asks nothing', async () => {
    renderAsk({ apiUrl: '' })

    expect(screen.getByText(text('ask.ui.noApi'))).toBeTruthy()
    expect((askButton() as HTMLButtonElement).disabled).toBe(true)
    expect((micButton() as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('switch', { name: text('ask.ui.location') }) as HTMLInputElement).disabled).toBe(true)
  })

  it('every line on the screen, and in each answer, keeps the copy rules', async () => {
    renderAsk()
    for (const question of ['Lusot ba sedan ko sa España cor. Maceda?', 'Kaya ba ng truck ko sa España cor. Maceda?', 'Baha ba sa Marikina?']) {
      await askTyped(question)
      await waitFor(() => expect(screen.queryByText(text('ask.ui.asking'))).toBeNull())
      expect(document.body.textContent).not.toMatch(BANNED_WORDS)
    }
  })
})
