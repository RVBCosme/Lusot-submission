// What the app's React root says about an error. By default React logs every error it reports, message and
// component stack included, and once screens hold report ids and positions those could reach the console (Global
// Constraints: never logged; S5-R6). So the root's three handlers log one line naming the error's class, and
// nothing the error carries: no message, no cause, no stack.
import type { RootOptions } from 'react-dom/client'

// A plain class name such as HttpError, or the kind of value thrown. A name that isn't a plain identifier could
// carry anything, so it reads as Error.
export function errorClass(error: unknown): string {
  if (error instanceof Error) return /^[A-Za-z]{1,40}$/.test(error.name) ? error.name : 'Error'
  return error === null ? 'null' : typeof error
}

// React calls each with the error and its component stack; the stack is left unread.
type Handler = (error: unknown, errorInfo: { componentStack?: string }) => void
type Handlers = Required<Pick<RootOptions, 'onCaughtError' | 'onUncaughtError' | 'onRecoverableError'>>

export const rootErrorOptions: { [Name in keyof Handlers]: Handler } = {
  onCaughtError: (error) => console.error(`Lusot: a screen failed (${errorClass(error)})`),
  onUncaughtError: (error) => console.error(`Lusot: the app failed (${errorClass(error)})`),
  onRecoverableError: (error) => console.error(`Lusot: React recovered from an error (${errorClass(error)})`),
}
