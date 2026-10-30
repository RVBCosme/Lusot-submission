import { makeT, useLanguage, useT, type Lang } from '../i18n'
import type { StringKey } from '../i18n/en'

// Each language's name comes from its own table and carries its own lang, whichever language the screen is in,
// so "English" reads as English and the Taglish name as Taglish (C619). About shows the same switch.
const OPTIONS: { lang: Lang; name: StringKey }[] = [
  { lang: 'en', name: 'lang.en' },
  { lang: 'fil', name: 'lang.fil' },
]

export function LanguageSwitch() {
  const { lang, setLang } = useLanguage()
  const label = useT()('lang.switch')
  return (
    <div role="group" aria-label={label.text} className="flex gap-1">
      {OPTIONS.map((option) => {
        const name = makeT(option.lang)(option.name)
        return (
          <button
            key={option.lang}
            type="button"
            lang={name.lang}
            aria-pressed={lang === option.lang}
            onClick={() => setLang(option.lang)}
            className="min-h-tap min-w-tap rounded-control border border-outline px-3 active:opacity-70 aria-pressed:border-action aria-pressed:bg-action aria-pressed:text-on-action aria-pressed:underline aria-pressed:decoration-2"
          >
            {name.text}
          </button>
        )
      })}
    </div>
  )
}
