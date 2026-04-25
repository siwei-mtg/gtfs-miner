import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AppShell } from '@/components/templates/AppShell'

describe('AppShell', () => {
  it('test_appshell_renders_header_when_user', () => {
    render(
      <AppShell
        user={{ id: '1', email: 'x@y.com', role: 'member', tenant_id: 't1', plan: 'free', created_at: '' }}
        onLogout={vi.fn()}
      >
        <div>content</div>
      </AppShell>
    )
    expect(screen.getByText('GTFS Miner')).toBeInTheDocument()
    expect(screen.getByText('x@y.com')).toBeInTheDocument()
  })

  it('test_appshell_hides_header_when_no_user', () => {
    render(
      <AppShell user={null} onLogout={vi.fn()}>
        <div>content</div>
      </AppShell>
    )
    expect(screen.queryByText('GTFS Miner')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /logout/i })).not.toBeInTheDocument()
  })

  it('test_appshell_hidden_on_auth_pages', () => {
    render(
      <AppShell user={null} onLogout={vi.fn()}>
        <div aria-label="login-page">Login Form</div>
      </AppShell>
    )
    expect(screen.queryByRole('banner')).not.toBeInTheDocument()
    expect(screen.getByLabelText('login-page')).toBeInTheDocument()
  })
})
