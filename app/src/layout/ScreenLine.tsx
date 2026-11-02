import { useT } from '../i18n'

// CLAUDE.md's line, on every screen (C608). Its key is locked, so it reads in English in both languages, and it
// carries lang="en" on an English screen and a Taglish one alike (C619). From lg it is the shell grid's last row, across
// the window; the footer around it hands it to the grid (Layout.tsx), so it keeps its own z-index above Leaflet's.
export function ScreenLine() {
  const line = useT()('layout.screenLine')
  return (
    <p lang={line.lang} className="border-t border-outline py-2 text-small lg:relative lg:z-[1100] lg:col-span-full lg:row-start-4 lg:bg-surface lg:px-4">
      {line.text}
    </p>
  )
}
