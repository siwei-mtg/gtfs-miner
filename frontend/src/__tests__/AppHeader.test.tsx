import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AppHeader } from '@/components/organisms/AppHeader'

describe('AppHeader', () => {
  it('test_appheader_shows_email', () => {
    render(<AppHeader email="user@example.com" onLogout={vi.fn()} />)
    expect(screen.getByText('user@example.com')).toBeInTheDocument()
  })

  it('test_logout_button_calls_handler', async () => {
    const onLogout = vi.fn()
    const user = userEvent.setup()
    render(<AppHeader email="user@example.com" onLogout={onLogout} />)
    await user.click(screen.getByRole('button', { name: /logout/i }))
    expect(onLogout).toHaveBeenCalledOnce()
  })
})
