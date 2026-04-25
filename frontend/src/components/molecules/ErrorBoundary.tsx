/**
 * ErrorBoundary — catches render-phase exceptions in a subtree and shows
 * the stack instead of letting React unmount everything to a blank screen.
 *
 * Intentionally kept as a class component: React Hooks can't capture
 * componentDidCatch yet (as of React 19).
 */
import React, { type ReactNode } from 'react'

interface Props {
  /** Labels the error banner so a page with multiple boundaries stays debuggable. */
  scope: string
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Surface via console so dev-tools / Vite overlay still picks it up.
    console.error(`[ErrorBoundary:${this.props.scope}]`, error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div
          role="alert"
          className="m-4 rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm"
        >
          <p className="font-semibold text-destructive">
            Erreur dans « {this.props.scope} »
          </p>
          <p className="mt-1 text-destructive">{this.state.error.message}</p>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">
            {this.state.error.stack}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}
