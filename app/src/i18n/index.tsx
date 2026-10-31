// The language module keeps its components and helpers together, as one import for every screen. Fast Refresh
// then reloads the page when this file changes, rather than updating it in place.
/* oxlint-disable react/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { readItem, writeItem } from '../lib/storage'
import { EN, type StringKey } from './en'
import { FIL } from './fil'

export type Lang = 'en' | 'fil'

// A line with the language it is in. Every helper that builds a line returns one, so a Taglish screen can mark
// an English line lang="en" (C619).
export type Text = { text: string; lang: Lang }

const LANG_KEY = 'lusot.lang'

// They stay in English in both languages until Rene decides otherwise (C619).
const LOCKED_KEYS: ReadonlySet<StringKey> = new Set<StringKey>(['layout.screenLine', 'about.notAffiliated'])

// Lines that bear on what a person does near water: the refusal, reason lines, retake tips, consent and the
// privacy policy. Ask Lusot's branch adds 'ask.answer.'.
const SCREEN_LINE_PREFIXES = ['refusal.', 'reason.', 'retake.', 'consent.', 'privacy.']

export function isScreenLineKey(key: StringKey): boolean {
  return SCREEN_LINE_PREFIXES.some((prefix) => key.startsWith(prefix))
}

// On a Taglish screen, the locked lines and the screen-line keys whose Taglish isn't reviewed show in English.
// Other draft Taglish lines show, so testers can react to them (C619).
export function resolveText(lang: Lang, key: StringKey): Text {
  const english: Text = { text: EN[key].text, lang: 'en' }
  if (lang === 'en' || LOCKED_KEYS.has(key)) return english
  const taglish = FIL[key]
  if (isScreenLineKey(key) && !taglish.reviewed) return english
  return { text: taglish.text, lang: 'fil' }
}

// Replaces each {name} that `vars` holds; any other {name} stays as written, so a missing value shows.
export function makeT(lang: Lang): (key: StringKey, vars?: Record<string, string | number>) => Text {
  return (key, vars) => {
    const line = resolveText(lang, key)
    if (vars === undefined) return line
    const text = line.text.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
      Object.hasOwn(vars, name) ? String(vars[name]) : placeholder,
    )
    return { text, lang: line.lang }
  }
}

type LanguageState = { lang: Lang; setLang(lang: Lang): void }

const LanguageContext = createContext<LanguageState | null>(null)

// English unless the phone keeps Taglish as the choice (C607, C619). The page's lang follows the choice.
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (readItem(LANG_KEY) === 'fil' ? 'fil' : 'en'))
  const setLang = useCallback((next: Lang) => {
    writeItem(LANG_KEY, next)
    setLangState(next)
  }, [])
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  const value = useMemo(() => ({ lang, setLang }), [lang, setLang])
  return <LanguageContext value={value}>{children}</LanguageContext>
}

export function useLanguage(): LanguageState {
  const state = useContext(LanguageContext)
  if (state === null) throw new Error('useLanguage needs a <LanguageProvider> above it')
  return state
}

export function useT(): ReturnType<typeof makeT> {
  const { lang } = useLanguage()
  return useMemo(() => makeT(lang), [lang])
}

// A line in the other language than the screen's carries its own lang, as WCAG 2.2's language of parts asks.
export function Line({ value }: { value: Text }) {
  const { lang } = useLanguage()
  return value.lang === lang ? value.text : <span lang={value.lang}>{value.text}</span>
}

export function T({ k, vars }: { k: StringKey; vars?: Record<string, string | number> }) {
  const t = useT()
  return <Line value={t(k, vars)} />
}

// The copy-review list (C609): every line, in either table, still waiting for Rene's review.
export function unreviewedKeys(): { lang: Lang; key: StringKey }[] {
  const keys = Object.keys(EN) as StringKey[]
  return [
    ...keys.filter((key) => !EN[key].reviewed).map((key) => ({ lang: 'en' as const, key })),
    ...keys.filter((key) => !FIL[key].reviewed).map((key) => ({ lang: 'fil' as const, key })),
  ]
}
