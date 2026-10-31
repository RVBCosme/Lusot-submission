import { useEffect, type RefObject } from 'react'

// A new screen, or new content on one, takes away the control that was pressed, and focus would fall to the page. This
// puts it on the screen's heading, where a screen reader starts reading, when it has fallen there (C612; the same
// pattern as the report screen's steps). Focus that is somewhere already stays there. `when` is what changes the
// content: the effect runs when it does, and once when the screen opens.
export function useHeadingFocus(heading: RefObject<HTMLElement | null>, when: unknown): void {
  useEffect(() => {
    const active = document.activeElement
    if (active !== null && active !== document.body) return
    const element = heading.current
    if (element === null) return
    element.setAttribute('tabindex', '-1')
    element.focus({ preventScroll: true })
  }, [heading, when])
}
