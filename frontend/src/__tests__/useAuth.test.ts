import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useAuth } from '../hooks/useAuth'
import * as apiClient from '../api/client'

vi.mock('../api/client', () => ({
  login: vi.fn(),
  register: vi.fn(),
  getMe: vi.fn(),
}))

describe('useAuth', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('test_initial_state_no_token', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.token).toBeNull()
    expect(result.current.user).toBeNull()
    expect(result.current.isLoading).toBe(false)
  })

  it('test_login_stores_token', async () => {
    vi.mocked(apiClient.login).mockResolvedValue({ access_token: 'new-token', token_type: 'bearer' })
    vi.mocked(apiClient.getMe).mockResolvedValue({ id: '1', email: 'test@t.com', role: 'member', tenant_id: '1', created_at: '2026' })

    const { result } = renderHook(() => useAuth())
    
    await act(async () => {
      await result.current.login('test@t.com', '123')
    })

    expect(localStorage.getItem('token')).toBe('new-token')
    expect(result.current.token).toBe('new-token')
  })

  it('test_logout_clears_token', async () => {
    localStorage.setItem('token', 'existing-token')
    vi.mocked(apiClient.getMe).mockResolvedValue({ id: '1', email: 'test@t.com', role: 'member', tenant_id: '1', created_at: '2026' })

    const { result } = renderHook(() => useAuth())
    
    await waitFor(() => {
      expect(result.current.user).not.toBeNull()
    })

    act(() => {
      result.current.logout()
    })

    expect(localStorage.getItem('token')).toBeNull()
    expect(result.current.token).toBeNull()
    expect(result.current.user).toBeNull()
  })

  it('test_restores_token_from_storage', async () => {
    localStorage.setItem('token', 'stored-token')
    vi.mocked(apiClient.getMe).mockResolvedValue({ id: '1', email: 'me@t.com', role: 'member', tenant_id: '1', created_at: '2026' })

    const { result } = renderHook(() => useAuth())
    
    expect(result.current.token).toBe('stored-token')
    
    await waitFor(() => {
      expect(result.current.user).not.toBeNull()
    })
    
    expect(result.current.user?.email).toBe('me@t.com')
  })

  it('test_login_failure_no_token', async () => {
    vi.mocked(apiClient.login).mockRejectedValue(new Error('Auth failed'))

    const { result } = renderHook(() => useAuth())
    
    await act(async () => {
      await expect(result.current.login('wrong@t.com', '123')).rejects.toThrow('Auth failed')
    })

    expect(localStorage.getItem('token')).toBeNull()
    expect(result.current.token).toBeNull()
  })

  it('test_user_loaded_after_login', async () => {
    vi.mocked(apiClient.login).mockResolvedValue({ access_token: 'login-token', token_type: 'bearer' })
    vi.mocked(apiClient.getMe).mockResolvedValue({ id: '1', email: 'login@t.com', role: 'member', tenant_id: '1', created_at: '2026' })

    const { result } = renderHook(() => useAuth())
    
    expect(result.current.user).toBeNull()

    await act(async () => {
      await result.current.login('login@t.com', 'pwd')
    })

    expect(result.current.user?.email).toBe('login@t.com')
    expect(result.current.isLoading).toBe(false)
  })
})
