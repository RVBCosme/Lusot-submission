import { useT } from '../i18n'

// CLAUDE.md's line, on every screen (C608). Its key is locked, so it reads in English in both languages, and it
// carries lang="en" on an English screen and a Taglish one alike (C619).
export function ScreenLine() {
  const line = useT()('layout.screenLine')
  return (
    <p lang={line.lang} className="border-t border-outline py-2 text-small">
      {line.text}
    </p>
  )
}
