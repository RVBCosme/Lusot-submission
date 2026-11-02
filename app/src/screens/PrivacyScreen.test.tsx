import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import consentText from '../content/consent.en.md?raw'
import privacyText from '../content/privacy.en.md?raw'
import { LanguageProvider } from '../i18n'
import { EN } from '../i18n/en'
import { FIL } from '../i18n/fil'
import { writeItem } from '../lib/storage'
import { PrivacyScreen } from './PrivacyScreen'

const PENDING = 'to be added before Lusot goes public'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
  localStorage.clear()
  document.documentElement.removeAttribute('lang')
})

function renderPolicy({ lang = 'en' }: { lang?: 'en' | 'fil' } = {}) {
  if (lang === 'fil') writeItem('lusot.lang', 'fil')
  render(
    <LanguageProvider>
      <PrivacyScreen />
    </LanguageProvider>,
  )
  return screen.getByTestId('policy')
}

describe('the privacy contact', () => {
  it.each([
    ['unset', undefined],
    ['empty', ''],
    ['blank', '   '],
  ])('%s, it reads "to be added before Lusot goes public" in both places', (_name, value) => {
    vi.stubEnv('VITE_PRIVACY_CONTACT', value)
    const policy = renderPolicy()

    expect(EN['privacy.contactPending'].text).toBe(PENDING)
    expect(policy.textContent?.split(`Contact: ${PENDING}.`)).toHaveLength(3)
    expect(policy.textContent).not.toContain('{privacyContact}')
  })

  it('set at build time, it shows the setting in both places', () => {
    vi.stubEnv('VITE_PRIVACY_CONTACT', 'the line set at build time')
    const policy = renderPolicy()

    expect(policy.textContent?.split('Contact: the line set at build time.')).toHaveLength(3)
    expect(policy.textContent).not.toContain(PENDING)
  })

  it('a setting that holds markup shows as text, never as markup', () => {
    vi.stubEnv('VITE_PRIVACY_CONTACT', '<b>desk</b> & <img src=x onerror=alert(1)>')
    const policy = renderPolicy()

    expect(policy.querySelector('b, img')).toBeNull()
    expect(policy.textContent).toContain('Contact: <b>desk</b> & <img src=x onerror=alert(1)>.')
  })

  it('the content file holds no address of its own, only the placeholder', () => {
    expect(privacyText.match(/\{privacyContact\}/g)).toHaveLength(2)
    expect(privacyText).not.toMatch(/\[privacy contact/)
  })
})

describe('the policy', () => {
  it('shows its title from the string table, "Not affiliated with MMDA.", and its sections from privacy.en.md', () => {
    const policy = renderPolicy()

    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(EN['privacy.title'].text)
    expect(screen.getAllByText('Not affiliated with MMDA.')).toHaveLength(1)
    expect(within(policy).queryByRole('heading', { level: 1 })).toBeNull()
    const sections = within(policy)
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent)
    expect(sections).toEqual([
      'Who runs Lusot',
      'Who can use Lusot',
      'What Lusot collects',
      'What happens to your photo',
      'What Meta keeps',
      'Public pins',
      'Ask Lusot',
      'Who processes data, and where',
      'How long Lusot keeps data',
      'Why Lusot may use this data',
      'Your rights',
      'Keeping data secure',
      'Changes to this policy',
    ])
    expect(within(policy).getAllByRole('table')).toHaveLength(3)
    expect(policy.textContent).not.toContain('Lusot estimates depth at one spot.')
    expect(policy.textContent).not.toContain('Not affiliated with MMDA.')
  })

  // CLAUDE.md's privacy rules, and Rene's Oct 29 and 30 decisions on hosting (MS5-Q4 (c), PRIV-Q9) and demo pins.
  it.each([
    ['faces are blurred before Meta receives the photo', /Faces are blurred automatically before Meta receives the photo\./],
    ['Meta may use what it receives to improve its products', /Meta may use what it receives to improve its products\./],
    ['plates are blurred before Lusot keeps a copy', /Faces and plates are blurred before Lusot keeps a copy\./],
    ['the original is deleted', /Lusot deletes your original photo as soon as the result is saved\./],
    ['data is kept 7 days', /7 days after the photo was taken/],
    ['there are no accounts and no names', /Lusot has no accounts\. It never asks for your name, email or phone number\./],
    // WebHosting=amplify: Rene's own line, Nov 2.
    ['the website host records each request', /When you open the Lusot website, our hosting service \(AWS Amplify\) records each request, including your IP address, the page asked for and the time\. Lusot doesn't use these records\. They are kept until the website is taken down after the hackathon's judging, by Dec 31, 2026\./],
    ['the access logs are kept until the take-down', /the website's access logs, kept by AWS Amplify: each request's IP address, page and time\s*until the website is taken down after the hackathon's judging, by Dec 31, 2026/],
    ['demo pins come from consented or openly licensed photos', /people who agreed to share their photos for this, or from openly licensed photos/],
    ['the credits ending pauses analysis and bills nothing', /When the credits run out, analysis pauses[\s\S]*Nothing is billed beyond the credits\./],
    ['Meta receives a spoken question\'s voice clip', /Meta receives a spoken question's voice clip and may keep it under its own terms\./],
    ['people in a photo are covered by the legitimate-interest basis', /People who appear in a photo haven't agreed to anything\. For them, Lusot relies on its legitimate interest in showing how deep the water is at one spot \(Section 12\(f\) of the Data Privacy Act\)/],
  ])('says %s', (_what, pattern) => {
    expect(renderPolicy().textContent).toMatch(pattern)
  })

  it('names Amplify only in its two website lines, keeps no CloudFront line, and has no "photos you take yourself"', () => {
    expect(privacyText.match(/amplify/gi)).toHaveLength(2)
    expect(privacyText).not.toMatch(/CloudFront|access logging is off/)
    expect(privacyText).not.toMatch(/yourself/i)
    expect(privacyText).not.toMatch(/MS5-Q4|PRIV-Q9/)
  })

  it('in Taglish, shows the policy in English, marked lang="en", under its reviewed title', () => {
    const policy = renderPolicy({ lang: 'fil' })

    expect(policy.getAttribute('lang')).toBe('en')
    expect(within(policy).getByRole('heading', { name: 'Who runs Lusot' })).toBeTruthy()
    const title = screen.getByRole('heading', { level: 1 })
    // The M20 review passed Window 4's title, which keeps the policy's name in English, so it needs no mark.
    expect(FIL['privacy.title'].reviewed).toBe(true)
    expect(title.textContent).toBe(FIL['privacy.title'].text)
    expect(title.querySelector('span')).toBeNull()
  })

  it('in Taglish, shows a title whose Taglish is not reviewed in English, marked lang="en"', () => {
    const reviewed = FIL['privacy.title']
    FIL['privacy.title'] = { text: 'Patakaran sa privacy ng Lusot', reviewed: false }
    try {
      renderPolicy({ lang: 'fil' })
      const title = screen.getByRole('heading', { level: 1 })
      expect(title.textContent).toBe(EN['privacy.title'].text)
      expect(title.querySelector('span')?.getAttribute('lang')).toBe('en')
    } finally {
      FIL['privacy.title'] = reviewed
    }
  })

  it('in Taglish, still reads the contact line in English in both places, as the policy itself is English', () => {
    vi.stubEnv('VITE_PRIVACY_CONTACT', undefined)
    const policy = renderPolicy({ lang: 'fil' })

    expect(FIL['privacy.contactPending'].text).toBe('idadagdag bago maging public ang Lusot')
    expect(policy.textContent?.split(`Contact: ${PENDING}.`)).toHaveLength(3)
    expect(policy.textContent).not.toContain(FIL['privacy.contactPending'].text)
  })
})

// The copy rules (C608) cover the two content files as they cover the string tables.
describe.each([
  ['consent.en.md', consentText],
  ['privacy.en.md', privacyText],
])('%s', (_name, text) => {
  it('holds no banned word or phrase', () => {
    expect(text).not.toMatch(/safe|ligtas/i)
    expect(text).not.toMatch(/you can cross|you can pass|go ahead|pu?wedeng dumaan|tumawid ka|lusutan mo/i)
    expect(text).not.toMatch(/MMDA(['’]?s)? (9|nine) levels|(the )?(9|nine) MMDA levels/i)
  })

  it('holds no email address and no raw HTML', () => {
    expect(text).not.toMatch(/[\w.+-]+@[\w-]+\.[\w.]+/)
    expect(text).not.toMatch(/<[a-z!/]/i)
  })
})
