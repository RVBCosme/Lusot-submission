import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import consentText from '../content/consent.en.md?raw'
import { LanguageProvider } from '../i18n'
import { EN } from '../i18n/en'
import { fnv1a32, GateProvider, hasNotice, isAdultConfirmed, NOTICE_VERSION, useGate } from './consent'

const CONSENT_KEY = 'lusot.consent'
const SCREEN_LINE = 'Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.'
const NOTICE_HEADING = 'Before your first photo'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  history.replaceState(null, '', '/')
  document.documentElement.removeAttribute('lang')
})

const stored = () => {
  const raw = localStorage.getItem(CONSENT_KEY)
  return raw === null ? null : (JSON.parse(raw) as unknown)
}
const store = (value: unknown) => localStorage.setItem(CONSENT_KEY, JSON.stringify(value))

// localStorage that throws on every access, as a blocked site's or some private windows' does.
function blockStorage() {
  vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
    throw new DOMException('The operation is insecure.', 'SecurityError')
  })
}

describe('NOTICE_VERSION', () => {
  it('fnv1a32 gives the published FNV-1a 32-bit values, as 8 hex digits', () => {
    expect(fnv1a32('')).toBe('811c9dc5')
    expect(fnv1a32('a')).toBe('e40c292c')
    expect(fnv1a32('foobar')).toBe('bf9cf968')
    // Over UTF-8 bytes, so ñ hashes as its two bytes (C3 B1), not as one UTF-16 unit (F1 gives 740b78dc).
    expect(fnv1a32('ñ')).toBe('069dc2f9')
  })

  it("is the hash of the notice's own text, so any change to the notice asks again", () => {
    expect(NOTICE_VERSION).toMatch(/^[0-9a-f]{8}$/)
    expect(NOTICE_VERSION).toBe(fnv1a32(consentText))
    expect(fnv1a32(`${consentText} `)).not.toBe(NOTICE_VERSION)
  })
})

describe('what the phone keeps', () => {
  it('nothing kept passes neither gate', () => {
    expect([isAdultConfirmed(), hasNotice()]).toEqual([false, false])
  })

  it('{ adult: true } passes the 18+ check only', () => {
    store({ adult: true })
    expect([isAdultConfirmed(), hasNotice()]).toEqual([true, false])
  })

  it('{ adult: true, notice: NOTICE_VERSION } passes both', () => {
    store({ adult: true, notice: NOTICE_VERSION })
    expect([isAdultConfirmed(), hasNotice()]).toEqual([true, true])
  })

  it('an older notice version passes the 18+ check, never the notice', () => {
    store({ adult: true, notice: NOTICE_VERSION === '00000000' ? '00000001' : '00000000' })
    expect([isAdultConfirmed(), hasNotice()]).toEqual([true, false])
  })

  it.each([
    ['not JSON', 'yes'],
    ['broken JSON', '{"adult":'],
    ['null', 'null'],
    ['an array', '[true]'],
    ['adult as a string', '{"adult":"true"}'],
    ['adult false with the notice', JSON.stringify({ adult: false, notice: NOTICE_VERSION })],
    ['the notice without adult', JSON.stringify({ notice: NOTICE_VERSION })],
  ])('%s passes neither gate', (_name, raw) => {
    localStorage.setItem(CONSENT_KEY, raw)
    expect([isAdultConfirmed(), hasNotice()]).toEqual([false, false])
  })

  it('storage that throws passes neither gate', () => {
    store({ adult: true, notice: NOTICE_VERSION })
    blockStorage()
    expect([isAdultConfirmed(), hasNotice()]).toEqual([false, false])
  })
})

// A screen with one button per gate, as the Tested page (adult) and Ask (notice) will have.
function Trigger({ kind, onRun }: { kind: 'adult' | 'notice'; onRun: () => void }) {
  const gate = useGate(kind)
  return (
    <button type="button" onClick={() => gate(onRun)}>
      Run {kind}
    </button>
  )
}

function renderGates() {
  const adult = vi.fn()
  const notice = vi.fn()
  render(
    <LanguageProvider>
      <GateProvider>
        <Trigger kind="adult" onRun={adult} />
        <Trigger kind="notice" onRun={notice} />
      </GateProvider>
    </LanguageProvider>,
  )
  return { adult, notice }
}

const run = (kind: 'adult' | 'notice') => fireEvent.click(screen.getByRole('button', { name: `Run ${kind}` }))
const continueButton = () => screen.getByRole('button', { name: EN['consent.continue'].text }) as HTMLButtonElement
const confirmAge = () => fireEvent.click(screen.getByRole('checkbox'))
const noticeShown = () => screen.queryByRole('heading', { level: 1, name: NOTICE_HEADING }) !== null
const ageCheckShown = () => screen.queryByRole('heading', { level: 1, name: EN['consent.adultTitle'].text }) !== null

describe('useGate', () => {
  it('the adult gate shows the 18+ check, stores { adult: true } and runs its action once', () => {
    const { adult } = renderGates()

    run('adult')

    expect(ageCheckShown()).toBe(true)
    expect(noticeShown()).toBe(false)
    expect(adult).not.toHaveBeenCalled()
    // The screen behind the gate stays mounted, out of sight and out of the accessibility tree.
    expect(screen.queryByRole('button', { name: 'Run adult' })).toBeNull()
    expect(continueButton().disabled).toBe(true)
    fireEvent.click(continueButton())
    expect(adult).not.toHaveBeenCalled()

    confirmAge()
    expect(continueButton().disabled).toBe(false)
    // A double tap: both clicks land before React re-renders and removes the gate.
    const button = continueButton()
    act(() => {
      button.click()
      button.click()
    })

    expect(adult).toHaveBeenCalledTimes(1)
    expect(stored()).toEqual({ adult: true })
    expect(ageCheckShown()).toBe(false)

    run('adult')
    expect(adult).toHaveBeenCalledTimes(2)
    expect(ageCheckShown()).toBe(false)
  })

  it('the notice gate shows the notice with the 18+ check, and stores { adult: true, notice: NOTICE_VERSION }', () => {
    const { notice } = renderGates()

    run('notice')

    expect(noticeShown()).toBe(true)
    expect(continueButton().disabled).toBe(true)
    confirmAge()
    fireEvent.click(continueButton())

    expect(notice).toHaveBeenCalledTimes(1)
    expect(stored()).toEqual({ adult: true, notice: NOTICE_VERSION })
    expect(noticeShown()).toBe(false)

    run('notice')
    expect(notice).toHaveBeenCalledTimes(2)
    expect(noticeShown()).toBe(false)
  })

  it('after the adult gate alone, the notice gate still shows the notice', () => {
    const { adult, notice } = renderGates()
    run('adult')
    confirmAge()
    fireEvent.click(continueButton())
    expect(adult).toHaveBeenCalledTimes(1)

    run('notice')

    expect(noticeShown()).toBe(true)
    expect(notice).not.toHaveBeenCalled()
  })

  it('after the notice gate, the adult gate passes at once', () => {
    const { adult } = renderGates()
    run('notice')
    confirmAge()
    fireEvent.click(continueButton())

    run('adult')

    expect(adult).toHaveBeenCalledTimes(1)
    expect(ageCheckShown()).toBe(false)
  })

  it('"Not now" runs nothing, stores nothing, and shows the screen again', () => {
    const { adult, notice } = renderGates()

    for (const kind of ['adult', 'notice'] as const) {
      run(kind)
      confirmAge()
      fireEvent.click(screen.getByRole('button', { name: EN['consent.notNow'].text }))
      expect(screen.getByRole('button', { name: `Run ${kind}` })).toBeTruthy()
    }

    expect(adult).not.toHaveBeenCalled()
    expect(notice).not.toHaveBeenCalled()
    expect(stored()).toBeNull()
  })

  it('a stored older notice version shows the notice again', () => {
    store({ adult: true, notice: NOTICE_VERSION === '00000000' ? '00000001' : '00000000' })
    const { adult, notice } = renderGates()

    run('notice')
    expect(noticeShown()).toBe(true)
    expect(notice).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: EN['consent.notNow'].text }))

    run('adult')
    expect(adult).toHaveBeenCalledTimes(1)
  })

  it('with storage blocked, the gates still work, and ask every time rather than fail open', () => {
    blockStorage()
    const { adult, notice } = renderGates()

    for (const [kind, action] of [
      ['adult', adult],
      ['notice', notice],
    ] as const) {
      for (const times of [1, 2]) {
        run(kind)
        expect(kind === 'adult' ? ageCheckShown() : noticeShown(), `${kind} asks, run ${times}`).toBe(true)
        confirmAge()
        fireEvent.click(continueButton())
        expect(action).toHaveBeenCalledTimes(times)
      }
    }
  })

  it('with writes refused but reads working, the gates ask every time', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('full', 'QuotaExceededError')
    })
    const { adult } = renderGates()

    run('adult')
    confirmAge()
    fireEvent.click(continueButton())
    run('adult')

    expect(adult).toHaveBeenCalledTimes(1)
    expect(ageCheckShown()).toBe(true)
  })

  it('moves focus to the gate, and back to the button that opened it', () => {
    renderGates()
    const button = screen.getByRole('button', { name: 'Run adult' })
    button.focus()

    run('adult')
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1 }))
    fireEvent.click(screen.getByRole('button', { name: EN['consent.notNow'].text }))

    expect(document.activeElement).toBe(button)
  })

  it('useGate outside a GateProvider fails loudly', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() =>
      render(
        <LanguageProvider>
          <Trigger kind="adult" onRun={() => {}} />
        </LanguageProvider>,
      ),
    ).toThrow(/GateProvider/)
  })
})

// The notice is enforced on the report screen itself, so a link, a bookmark or a typed #/report all meet it (C605).
describe('the report route', () => {
  const API = 'https://api.example.test'
  const reportHeading = () => screen.queryByRole('heading', { level: 1, name: EN['nav.report'].text })

  function renderReport() {
    history.replaceState(null, '', '/#/report')
    return render(<App apiUrl={API} />)
  }

  it('a typed #/report on the first visit shows the notice in place of the screen, under the screen line', () => {
    renderReport()

    expect(noticeShown()).toBe(true)
    expect(reportHeading()).toBeNull()
    expect(document.body.textContent?.split(SCREEN_LINE)).toHaveLength(2)
    expect(screen.getByRole('main').contains(screen.getByRole('heading', { level: 1 }))).toBe(true)
  })

  it('"Continue" after the 18+ box opens the report screen, and the next visit goes straight to it', () => {
    const first = renderReport()
    expect(continueButton().disabled).toBe(true)
    confirmAge()
    fireEvent.click(continueButton())

    expect(reportHeading()).toBeTruthy()
    expect(stored()).toEqual({ adult: true, notice: NOTICE_VERSION })

    first.unmount()
    renderReport()
    expect(reportHeading()).toBeTruthy()
    expect(noticeShown()).toBe(false)
  })

  it('after the 18+ check alone, #/report still shows the notice', () => {
    store({ adult: true })
    renderReport()
    expect(noticeShown()).toBe(true)
    expect(reportHeading()).toBeNull()
  })

  it('a stored older notice version shows the notice again', () => {
    store({ adult: true, notice: NOTICE_VERSION === '00000000' ? '00000001' : '00000000' })
    renderReport()
    expect(noticeShown()).toBe(true)
    expect(reportHeading()).toBeNull()
  })

  it('"Not now" goes to the map and stores nothing', () => {
    renderReport()
    confirmAge()

    fireEvent.click(screen.getByRole('button', { name: EN['consent.notNow'].text }))

    expect(window.location.hash).toBe('#/map')
    expect(stored()).toBeNull()
  })

  it('with storage blocked, the notice shows, "Continue" opens the screen, and the next visit asks again', () => {
    blockStorage()
    const first = renderReport()
    expect(noticeShown()).toBe(true)
    confirmAge()
    fireEvent.click(continueButton())
    expect(reportHeading()).toBeTruthy()

    first.unmount()
    renderReport()
    expect(noticeShown()).toBe(true)
    expect(reportHeading()).toBeNull()
  })
})
