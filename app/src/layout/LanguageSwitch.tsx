import { makeT, useLanguage, useT, type Lang } from '../i18n'
import type { StringKey } from '../i18n/en'

// Each language's name comes from its own table and carries its own lang, whichever language the screen is in,
// so "English" reads as English and the Taglish name as Taglish (C619). About shows the same switch. A press fills
// the button with ink and turns its text to the page's colour, a pair far above 4.5:1 in both themes, rather than
// fading the selected button's text below it (S5-R6).
//
// In the top bar (`onBrand`) the switch sits on the brand navy, so it takes the brand's pale colours, which hold 4.5:1
// there (styles/contrast.test.ts): a dim edge, pale text, and the chosen language filled in pale with navy text and still
// underlined, so the choice is never told by colour alone.
const OPTIONS: { lang: Lang; name: StringKey }[] = [
  { lang: 'en', name: 'lang.en' },
  { lang: 'fil', name: 'lang.fil' },
]

const BUTTON = 'min-h-tap min-w-tap rounded-control border px-3'
const ON_PAGE =
  'border-outline aria-pressed:border-action aria-pressed:bg-action aria-pressed:text-on-action aria-pressed:underline aria-pressed:decoration-2 active:border-ink active:bg-ink active:text-surface aria-pressed:active:border-ink aria-pressed:active:bg-ink aria-pressed:active:text-surface'
const ON_BRAND =
  'border-brand-dim text-brand-pale aria-pressed:border-brand-pale aria-pressed:bg-brand-pale aria-pressed:text-brand-navy aria-pressed:underline aria-pressed:decoration-2 active:bg-brand-line aria-pressed:active:bg-brand-mist'

export function LanguageSwitch({ className, onBrand = false }: { className?: string; onBrand?: boolean }) {
  const { lang, setLang } = useLanguage()
  const label = useT()('lang.switch')
  return (
    <div role="group" aria-label={label.text} className={className === undefined ? 'flex gap-1' : `flex gap-1 ${className}`}>
      {OPTIONS.map((option) => {
        const name = makeT(option.lang)(option.name)
        return (
          <button
            key={option.lang}
            type="button"
            lang={name.lang}
            aria-pressed={lang === option.lang}
            onClick={() => setLang(option.lang)}
            className={`${BUTTON} ${onBrand ? ON_BRAND : ON_PAGE}`}
          >
            {name.text}
          </button>
        )
      })}
    </div>
  )
}
