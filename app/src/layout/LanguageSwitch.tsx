import { makeT, useLanguage, useT, type Lang } from '../i18n'
import type { StringKey } from '../i18n/en'

// Each language's name comes from its own table and carries its own lang, whichever language the screen is in,
// so "English" reads as English and the Taglish name as Taglish (C619). About shows the same switch. A press fills
// the button with ink and turns its text to the page's colour, a pair far above 4.5:1 in both themes, rather than
// fading the selected button's text below it (S5-R6).
const OPTIONS: { lang: Lang; name: StringKey }[] = [
  { lang: 'en', name: 'lang.en' },
  { lang: 'fil', name: 'lang.fil' },
]

export function LanguageSwitch({ className }: { className?: string }) {
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
            className="min-h-tap min-w-tap rounded-control border border-outline px-3 aria-pressed:border-action aria-pressed:bg-action aria-pressed:text-on-action aria-pressed:underline aria-pressed:decoration-2 active:border-ink active:bg-ink active:text-surface aria-pressed:active:border-ink aria-pressed:active:bg-ink aria-pressed:active:text-surface"
          >
            {name.text}
          </button>
        )
      })}
    </div>
  )
}
