import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// maplibre-gl executes `window.URL.createObjectURL(new Blob(...))` at module
// load time, which jsdom does not support.  Stub it before App (which
// transitively imports MapView) is imported.  vi.mock is hoisted.
vi.mock('maplibre-gl', () => ({
  default: {
    Map: vi.fn(() => ({
      on: vi.fn(), addSource: vi.fn(), addLayer: vi.fn(), getLayer: vi.fn(() => true),
      setLayoutProperty: vi.fn(), remove: vi.fn(), addControl: vi.fn(), resize: vi.fn(),
    })),
    NavigationControl: vi.fn(),
    Marker: vi.fn(() => ({ setLngLat: vi.fn().mockReturnThis(), addTo: vi.fn().mockReturnThis(), remove: vi.fn() })),
    Popup: vi.fn(() => ({ setLngLat: vi.fn().mockReturnThis(), setHTML: vi.fn().mockReturnThis(), addTo: vi.fn().mockReturnThis(), remove: vi.fn() })),
  },
}))

import App from '../App'
import * as client from '../api/client'
import * as useProjectProgressModule from '../hooks/useProjectProgress'
import * as useAuthModule from '../hooks/useAuth'

vi.mock('../api/client', () => ({
  createProject: vi.fn(),
  uploadGtfs: vi.fn(),
  listProjects: vi.fn(),
  getTableData: vi.fn(),
  getTableDownloadUrl: vi.fn(),
  getJourTypes: vi.fn().mockResolvedValue([]),
}))

vi.mock('../hooks/useProjectProgress', () => ({
  useProjectProgress: vi.fn()
}))

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn()
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useProjectProgressModule.useProjectProgress).mockReturnValue({
    messages: [],
    latestStatus: null,
    isConnected: false
  })
  window.history.pushState({}, '', '/')
})

describe('App Routing & State Machine', () => {
  it('test_redirects_to_login_if_unauthenticated', async () => {
    vi.mocked(useAuthModule.useAuth).mockReturnValue({
      token: null, isLoading: false, user: null, login: vi.fn(), logout: vi.fn(), register: vi.fn()
    } as any)
    
    render(<App />)
    
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Login/i })).toBeInTheDocument()
    })
  })

  it('test_shows_project_list_when_authenticated', async () => {
    vi.mocked(useAuthModule.useAuth).mockReturnValue({
      token: 'valid-token', isLoading: false, user: { id: 'u1' } as any, login: vi.fn(), logout: vi.fn(), register: vi.fn()
    })
    vi.mocked(client.listProjects).mockResolvedValue([{
      id: 'proj-auth', status: 'completed', created_at: '2026', updated_at: '2026', parameters: {} as any, error_message: null
    }])
    
    render(<App />)
    
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /My Projects/i })).toBeInTheDocument()
      expect(screen.getByText('proj-auth')).toBeInTheDocument()
    })
  })

  it('test_navigates_to_project_detail', async () => {
    vi.mocked(useAuthModule.useAuth).mockReturnValue({
      token: 'valid-token', isLoading: false, user: { id: 'u1' } as any, login: vi.fn(), logout: vi.fn(), register: vi.fn()
    })
    vi.mocked(client.listProjects).mockResolvedValue([{
      id: 'proj-nav', status: 'completed', created_at: '2026', updated_at: '2026', parameters: {} as any, error_message: null
    }])
    
    const user = userEvent.setup()
    render(<App />)
    
    await waitFor(() => expect(screen.getByText('proj-nav')).toBeInTheDocument())
    
    await user.click(screen.getByText('proj-nav'))
    
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Project proj-nav/i })).toBeInTheDocument()
    })
  })

  it('test_logout_clears_session', async () => {
    const logoutMock = vi.fn()
    vi.mocked(useAuthModule.useAuth).mockReturnValue({
      token: 'valid-token', isLoading: false, user: { id: 'u1', email: 'u@test.com' } as any, login: vi.fn(), logout: logoutMock, register: vi.fn()
    })
    vi.mocked(client.listProjects).mockResolvedValue([])

    const user = userEvent.setup()
    render(<App />)
    
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Logout/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /Logout/i }))
    expect(logoutMock).toHaveBeenCalled()
  })

  it('test_dashboard_route_redirects_unauthenticated', async () => {
    vi.mocked(useAuthModule.useAuth).mockReturnValue({
      token: null, isLoading: false, user: null, login: vi.fn(), logout: vi.fn(), register: vi.fn(),
    } as any)
    window.history.pushState({}, '', '/projects/p1/dashboard')

    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Login/i })).toBeInTheDocument()
    })
  })

  it('test_new_project_flow', async () => {
    vi.mocked(useAuthModule.useAuth).mockReturnValue({
      token: 'valid-token', isLoading: false, user: { id: 'u1' } as any, login: vi.fn(), logout: vi.fn(), register: vi.fn()
    })
    vi.mocked(client.listProjects).mockResolvedValue([])
    vi.mocked(client.createProject).mockResolvedValue({
      id: 'new-proj', status: 'pending', created_at: '2026', updated_at: '2026', parameters: {} as any, error_message: null
    })
    vi.mocked(client.uploadGtfs).mockResolvedValue({ msg: 'ok', project_id: 'new-proj' })

    const user = userEvent.setup()
    render(<App />)

    await waitFor(() => expect(screen.getByRole('button', { name: /New Project/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /New Project/i }))

    await waitFor(() => expect(screen.getByLabelText('GTFS ZIP')).toBeInTheDocument())

    await user.upload(
      screen.getByLabelText('GTFS ZIP'),
      new File(['zip'], 'gtfs.zip', { type: 'application/zip' })
    )
    await user.click(screen.getByRole('button', { name: /Lancer le traitement/i }))

    await waitFor(() => {
      expect(client.createProject).toHaveBeenCalled()
      expect(client.uploadGtfs).toHaveBeenCalled()
      expect(screen.getByRole('heading', { name: /Project new-proj/i })).toBeInTheDocument()
    })
  })
})
