import type { ProjectCreate, ProjectResponse, UploadResponse } from '../types/api'

function normalizeOrigin(raw: string | undefined): string {
  if (!raw) return ''
  const s = raw.replace(/\/$/, '')
  return /^https?:\/\//.test(s) ? s : `https://${s}`
}
const API_ORIGIN = normalizeOrigin(import.meta.env.VITE_API_URL as string | undefined)
const BASE = `${API_ORIGIN}/api/v1/projects`

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
