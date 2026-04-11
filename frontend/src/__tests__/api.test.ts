import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createProject, uploadGtfs, getProject, getDownloadUrl, register, login, getMe } from '../api/client'
import type { ProjectCreate, UserCreate, Token, UserResponse } from '../types/api'

const defaultParams: ProjectCreate = {
  hpm_debut: '07:00',
  hpm_fin: '09:00',
  hps_debut: '17:00',
  hps_fin: '19:30',
  vacances: 'A',
  pays: '法国',
}

const mockProject = {
  id: 'test-uuid',
  status: 'pending' as const,
  created_at: '2026-04-07T00:00:00',
  updated_at: '2026-04-07T00:00:00',
  parameters: defaultParams,
  error_message: null,
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('createProject', () => {
  it('POSTs to /api/v1/projects/ with JSON body', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(mockProject), { status: 200 })
    )

    const result = await createProject(defaultParams)

    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/projects/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(defaultParams),
    })
    expect(result.id).toBe('test-uuid')
  })

  it('throws on non-ok response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('', { status: 422 })
    )
    await expect(createProject(defaultParams)).rejects.toThrow('createProject failed: 422')
  })
})

describe('uploadGtfs', () => {
  it('POSTs FormData to /api/v1/projects/{id}/upload', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ msg: 'ok', project_id: 'test-uuid' }), { status: 200 })
    )

    const file = new File(['zip-content'], 'gtfs.zip', { type: 'application/zip' })
    const result = await uploadGtfs('test-uuid', file)

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/v1/projects/test-uuid/upload',
      expect.objectContaining({ method: 'POST' })
    )
    const [, init] = fetchSpy.mock.calls[0]
    expect((init as RequestInit).body).toBeInstanceOf(FormData)
    expect(result.project_id).toBe('test-uuid')
  })
})

describe('getProject', () => {
  it('GETs /api/v1/projects/{id}', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(mockProject), { status: 200 })
    )

    const result = await getProject('test-uuid')

    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/projects/test-uuid', {
      headers: {}
    })
    expect(result.status).toBe('pending')
  })

  it('throws on 404', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('', { status: 404 })
    )
    await expect(getProject('missing')).rejects.toThrow('getProject failed: 404')
  })
})

describe('getDownloadUrl', () => {
  it('returns correct download URL', () => {
    expect(getDownloadUrl('test-uuid')).toBe('/api/v1/projects/test-uuid/download')
  })
})

describe('register', () => {
  it('test_register_call', async () => {
    const mockToken: Token = { access_token: 'fake-token', token_type: 'bearer' }
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(mockToken), { status: 201 })
    )

    const payload: UserCreate = { email: 'u@test.com', password: '123', tenant_name: 't' }
    const result = await register(payload)

    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    expect(result.access_token).toBe('fake-token')
  })
})

describe('login', () => {
  it('test_login_call', async () => {
    const mockToken: Token = { access_token: 'fake-token', token_type: 'bearer' }
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(mockToken), { status: 200 })
    )

    const result = await login('u@test.com', '123')

    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({
      method: 'POST'
    }))
    const [, init] = fetchSpy.mock.calls[0]
    expect((init as RequestInit).body).toBeInstanceOf(URLSearchParams)
    const bodyParams = (init as RequestInit).body as URLSearchParams
    expect(bodyParams.get('username')).toBe('u@test.com')
    expect(bodyParams.get('password')).toBe('123')
    expect(result.access_token).toBe('fake-token')
  })
})

describe('getMe', () => {
  it('test_getMe_with_auth_header', async () => {
    const mockUser: UserResponse = { id: '1', email: 'u@test.com', role: 'member', tenant_id: '1', created_at: '2026' }
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(mockUser), { status: 200 })
    )

    const result = await getMe('fake-token')

    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/auth/me', {
      headers: { 'Authorization': 'Bearer fake-token' }
    })
    expect(result.email).toBe('u@test.com')
  })
})
