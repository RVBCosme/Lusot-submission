import { Marked } from 'marked'
import { useMemo } from 'react'
import type { Lang } from '../i18n'

// Its own instance, so no option or extension set elsewhere reaches it.
const marked = new Marked({ gfm: true, async: false })

// The prose styles, all from the tokens. A table fits the screen's width in equal columns, at the small size, and
// breaks only a word longer than its column, rather than scroll sideways: a scrolling box with nothing focusable in
// it is out of a keyboard's reach. Tailwind finds classes by reading this file, so each is written out in full.
const PROSE = [
  '[&_h1]:text-title [&_h1]:font-bold',
  '[&_h2]:mt-6 [&_h2]:text-heading [&_h2]:font-bold',
  '[&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:mt-3 [&_ol]:list-decimal [&_ol]:pl-6',
  '[&_li]:mt-2 [&_li>ul]:mt-2 [&_strong]:font-bold',
  '[&_table]:mt-3 [&_table]:w-full [&_table]:table-fixed [&_table]:border-collapse [&_table]:text-small',
  '[&_th]:border [&_th]:border-outline [&_th]:p-2 [&_th]:text-left [&_th]:align-top [&_th]:hyphens-auto [&_th]:wrap-break-word',
  '[&_td]:border [&_td]:border-outline [&_td]:p-2 [&_td]:text-left [&_td]:align-top [&_td]:hyphens-auto [&_td]:wrap-break-word',
].join(' ')

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }
const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (char) => ESCAPES[char])

// Renders one of the app's own Markdown files (app/src/content/), never text a person typed, so marked's HTML goes
// in as it is. Each {name} that `vars` holds is filled after rendering, escaped, so a value is always text and
// never Markdown or markup. `lang` is the file's language, which a Taglish screen marks (C619).
export function Markdown({
  source,
  lang,
  vars = {},
  className = '',
  testId,
}: {
  source: string
  lang: Lang
  vars?: Record<string, string>
  className?: string
  testId?: string
}) {
  const rendered = useMemo(() => marked.parse(source, { async: false }), [source])
  const html = rendered.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    Object.hasOwn(vars, name) ? escapeHtml(vars[name]) : placeholder,
  )
  return (
    <div lang={lang} data-testid={testId} className={`${PROSE} ${className}`} dangerouslySetInnerHTML={{ __html: html }} />
  )
}
