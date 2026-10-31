import { useId, useState, type ReactNode } from 'react'
import { T } from '../i18n'
import type { StringKey } from '../i18n/en'
import { LanguageSwitch } from '../layout/LanguageSwitch'
import { OFFICIAL_SITES } from '../lib/officialSites'
import { chooseTheme, currentTheme, type Theme } from '../lib/theme'

const THEMES: { theme: Theme; label: StringKey }[] = [
  { theme: 'system', label: 'about.theme.system' },
  { theme: 'light', label: 'about.theme.light' },
  { theme: 'dark', label: 'about.theme.dark' },
]

const LINK = 'inline-flex min-h-tap min-w-tap items-center text-action underline underline-offset-4'
const HEADING = 'text-heading font-bold'

function Section({ title, children }: { title: StringKey; children: ReactNode }) {
  const id = useId()
  return (
    <section aria-labelledby={id} className="mt-8">
      <h2 id={id} className={HEADING}>
        <T k={title} />
      </h2>
      {children}
    </section>
  )
}

// Three options as one row of buttons, like the language switch: native radios, so arrow keys move between them,
// hidden behind their labels, which draw the choice and the focus ring. A press fills an option with ink (S5-R6).
function ThemeChoice() {
  const name = useId()
  const [theme, setTheme] = useState(currentTheme)
  return (
    <fieldset className="mt-8">
      <legend>
        <h2 className={HEADING}>
          <T k="about.theme" />
        </h2>
      </legend>
      <div className="mt-2 flex flex-wrap gap-1">
        {THEMES.map((option) => (
          <label
            key={option.theme}
            className="flex min-h-tap min-w-tap cursor-pointer items-center rounded-control border border-outline px-3 has-[:checked]:border-action has-[:checked]:bg-action has-[:checked]:text-on-action has-[:checked]:underline has-[:checked]:decoration-2 has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus has-[:focus-visible]:outline-solid active:border-ink active:bg-ink active:text-surface"
          >
            <input
              type="radio"
              name={name}
              value={option.theme}
              checked={theme === option.theme}
              onChange={() => {
                chooseTheme(option.theme)
                setTheme(option.theme)
              }}
              className="sr-only"
            />
            <T k={option.label} />
          </label>
        ))}
      </div>
    </fieldset>
  )
}

// What Lusot is, the language and theme, MMDA's and PAGASA's sites, the credits with "Not affiliated with MMDA.",
// and the links to the privacy policy and the licences (spec §4.1; C619, C633, C636).
export function AboutScreen() {
  return (
    <div className="max-w-prose">
      <h1 className="text-title font-bold">
        <T k="nav.about" />
      </h1>
      <p className="mt-3">
        <T k="about.what" />
      </p>

      <Section title="lang.switch">
        <div className="mt-2">
          <LanguageSwitch />
        </div>
      </Section>

      <ThemeChoice />

      <Section title="about.officialTitle">
        <ul className="mt-1">
          {OFFICIAL_SITES.map(({ href, label }) => (
            <li key={href}>
              <a href={href} className={LINK}>
                <T k={label} />
              </a>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="about.creditsTitle">
        <p className="mt-2">
          <T k="about.credits.maker" />
        </p>
        <p className="mt-2">
          <T k="about.credits.models" />
        </p>
        <p className="mt-2">
          <T k="about.credits.levels" />
        </p>
        <p className="mt-2 text-ink-2">
          <T k="about.notAffiliated" />
        </p>
      </Section>

      <Section title="about.legalTitle">
        <ul className="mt-1">
          <li>
            <a href="#/privacy" className={LINK}>
              <T k="privacy.title" />
            </a>
          </li>
          <li>
            <a href="#/licences" className={LINK}>
              <T k="licences.title" />
            </a>
          </li>
        </ul>
      </Section>
    </div>
  )
}
