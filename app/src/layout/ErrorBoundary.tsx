import { Component, type ReactNode } from 'react'
import { T } from '../i18n'

type State = { failed: boolean }

// Around the routed screen inside <main>, never around the layout, so a screen that crashes costs the screen and
// nothing else: the header, the nav and the screen line stay (S5-R5). Layout keys <main> by route, so going to
// another screen mounts a fresh boundary. The fallback says nothing about the error, which may hold anything, and
// React reports the error itself; this file logs nothing.
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" className="rounded-control border border-outline p-2">
        <p>
          <T k="layout.errorFallback" />
        </p>
      </div>
    )
  }
}
