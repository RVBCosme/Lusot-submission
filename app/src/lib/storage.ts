// The app's only on-device storage (C607). localStorage can be missing or throw (blocked site data, a private
// window, a full quota), and losing it costs only a repeated choice, so every call swallows the error.

export function readItem(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Not kept; the app works without it.
  }
}

export function removeItem(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // Nothing to remove from storage that can't be reached.
  }
}
