import type { ProjectCreate, ProjectResponse, UploadResponse, UserCreate, Token, UserResponse } from '../types/api'

function normalizeOrigin(raw: string | undefined): string {
  if (!raw) return ''
  const s = raw.replace(/\/$/, '')
  return /^https?:\/\//.test(s) ? s : `https://${s}`
}
const API_ORIGIN = normalizeOrigin(import.meta.env.VITE_API_URL as string | undefined)
const BASE = `${API_ORIGIN}/api/v1/projects`
const AUTH_BASE = `${API_ORIGIN}/api/v1/auth`

export async function createProject(params: ProjectCreate): Promise<ProjectResponse> {
  const res = await fetch(`${BASE}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
    body: form,
  })
  if (!res.ok) throw new Error(`uploadGtfs failed: ${res.status}`)
  return res.json()
}

export async function getProject(projectId: string): Promise<ProjectResponse> {
  const res = await fetch(`${BASE}/${projectId}`)
  if (!res.ok) throw new Error(`getProject failed: ${res.status}`)
  return res.json()
}

export function getDownloadUrl(projectId: string): string {
  return `${BASE}/${projectId}/download`
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
