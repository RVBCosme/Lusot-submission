import type { ReactNode } from 'react'

// A small mark that says what kind of card this is: "Sample" or "Demo" (spec §4.1). It is a word in an edge, never a
// colour, so it reads the same in either theme and to anyone who can't tell colours apart.
export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex min-h-8 items-center rounded-control border-2 border-outline px-2 text-small font-bold">
      {children}
    </span>
  )
}
