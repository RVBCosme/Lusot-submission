import { readItem, writeItem } from './storage'

// The theme the person picks on About (C624): the device's setting, or light or dark whatever it says. tokens.css
// reads data-theme on <html>; with no attribute, prefers-color-scheme decides.
export type Theme = 'system' | 'light' | 'dark'

const THEME_KEY = 'lusot.theme'

const asTheme = (value: string | null | undefined): Theme => (value === 'light' || value === 'dark' ? value : 'system')

// The choice kept on the phone (C607), or the system when none is kept or storage can't be read.
export function storedTheme(): Theme {
  return asTheme(readItem(THEME_KEY))
}

// The theme in use now. It holds even when storage is blocked and the choice wasn't kept.
export function currentTheme(): Theme {
  return asTheme(document.documentElement.dataset.theme)
}

export function applyTheme(theme: Theme): void {
  if (theme === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.dataset.theme = theme
}

export function chooseTheme(theme: Theme): void {
  writeItem(THEME_KEY, theme)
  applyTheme(theme)
}
