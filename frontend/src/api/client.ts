import type { ProjectCreate, ProjectResponse, UploadResponse, UserCreate, Token, UserResponse, TableDataResponse } from '../types/api'

function normalizeOrigin(raw: string | undefined): string {
  if (!raw) return ''
  const s = raw.replace(/\/$/, '')
  return /^https?:\/\//.test(s) ? s : `https://${s}`
}
const API_ORIGIN = normalizeOrigin(import.meta.env.VITE_API_URL as string | undefined)
const BASE = `${API_ORIGIN}/api/v1/projects`
const AUTH_BASE = `${API_ORIGIN}/api/v1/auth`

function getAuthHeaders(headers: HeadersInit = {}): HeadersInit {
  const token = localStorage.getItem('token')
  return token ? { ...headers, Authorization: `Bearer ${token}` } : headers
}

export async function createProject(params: ProjectCreate): Promise<ProjectResponse> {
  const res = await fetch(`${BASE}/`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(`createProject failed: ${res.status}`)
  return res.json()
}

export async function uploadGtfs(projectId: string, file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/${projectId}/upload`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: form,
  })
  if (!res.ok) throw new Error(`uploadGtfs failed: ${res.status}`)
  return res.json()
}

export async function getProject(projectId: string): Promise<ProjectResponse> {
  const res = await fetch(`${BASE}/${projectId}`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`getProject failed: ${res.status}`)
  return res.json()
}

export async function listProjects(): Promise<ProjectResponse[]> {
  const res = await fetch(`${BASE}/`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`listProjects failed: ${res.status}`)
  return res.json()
}

export function getDownloadUrl(projectId: string): string {
  return `${BASE}/${projectId}/download`
}

export async function getTableData(
  projectId: string,
  tableName: string,
  params: { skip?: number; limit?: number; sort_by?: string; sort_order?: string; q?: string }
): Promise<TableDataResponse> {
  const query = new URLSearchParams()
  if (params.skip !== undefined) query.append('skip', params.skip.toString())
  if (params.limit !== undefined) query.append('limit', params.limit.toString())
  if (params.sort_by) query.append('sort_by', params.sort_by)
  if (params.sort_order) query.append('sort_order', params.sort_order)
  if (params.q) query.append('q', params.q)

  const res = await fetch(`${BASE}/${projectId}/tables/${tableName}?${query.toString()}`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`getTableData failed: ${res.status}`)
  return res.json()
}

export function getTableDownloadUrl(projectId: string, tableName: string): string {
  return `${BASE}/${projectId}/tables/${tableName}/download`
}

export async function register(data: UserCreate): Promise<Token> {
  const res = await fetch(`${AUTH_BASE}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`register failed: ${res.status}`)
  return res.json()
}

export async function login(email: string, password: string): Promise<Token> {
  const params = new URLSearchParams()
  params.append('username', email)
  params.append('password', password)

  const res = await fetch(`${AUTH_BASE}/login`, {
    method: 'POST',
    body: params,
  })
  if (!res.ok) throw new Error(`login failed: ${res.status}`)
  return res.json()
}

export async function getMe(token: string): Promise<UserResponse> {
  const res = await fetch(`${AUTH_BASE}/me`, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
  if (!res.ok) throw new Error(`getMe failed: ${res.status}`)
  return res.json()
}
