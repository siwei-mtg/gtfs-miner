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

async function fetchBlob(url: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(url, { headers: getAuthHeaders() })
  if (!res.ok) throw new Error(`Download failed: ${res.status}`)
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = disposition.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : 'download'
  return { blob: await res.blob(), filename }
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadProjectResults(projectId: string): Promise<void> {
  const { blob, filename } = await fetchBlob(`${BASE}/${projectId}/download`)
  triggerBlobDownload(blob, filename)
}

export interface TableQueryParams {
  skip?: number
  limit?: number
  sort_by?: string
  sort_order?: string
  q?: string
  /** Task 38A: SQL IN (...) on an enum-like column. */
  filter_field?: string
  filter_values?: string[]
  /** Task 38A: inclusive numeric range [min, max]. */
  range_field?: string
  range_min?: number
  range_max?: number
}

export async function getTableData(
  projectId: string,
  tableName: string,
  params: TableQueryParams,
): Promise<TableDataResponse> {
  const query = new URLSearchParams()
  if (params.skip !== undefined) query.append('skip', params.skip.toString())
  if (params.limit !== undefined) query.append('limit', params.limit.toString())
  if (params.sort_by) query.append('sort_by', params.sort_by)
  if (params.sort_order) query.append('sort_order', params.sort_order)
  if (params.q) query.append('q', params.q)
  if (params.filter_field && params.filter_values && params.filter_values.length > 0) {
    query.append('filter_field', params.filter_field)
    query.append('filter_values', params.filter_values.join(','))
  }
  if (params.range_field && (params.range_min !== undefined || params.range_max !== undefined)) {
    query.append('range_field', params.range_field)
    if (params.range_min !== undefined) query.append('range_min', params.range_min.toString())
    if (params.range_max !== undefined) query.append('range_max', params.range_max.toString())
  }

  const res = await fetch(`${BASE}/${projectId}/tables/${tableName}?${query.toString()}`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`getTableData failed: ${res.status}`)
  return res.json()
}

export async function downloadTableCsv(projectId: string, tableName: string): Promise<void> {
  const { blob, filename } = await fetchBlob(`${BASE}/${projectId}/tables/${tableName}/download`)
  triggerBlobDownload(blob, filename)
}

export async function downloadGeoPackage(projectId: string, jourType: number): Promise<void> {
  const { blob } = await fetchBlob(`${BASE}/${projectId}/export/geopackage?jour_type=${jourType}`)
  triggerBlobDownload(blob, `${projectId}.gpkg`)
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

export interface JourTypeOption {
  value: number
  label: string
}

export async function getJourTypes(projectId: string): Promise<JourTypeOption[]> {
  const res = await fetch(`${BASE}/${projectId}/map/jour-types`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`getJourTypes failed: ${res.status}`)
  return res.json()
}

export interface PeakOffpeakRow {
  id_ag_num: number
  stop_name: string
  peak_count: number
  offpeak_count: number
}

export async function getPeakOffpeak(
  projectId: string,
  jourType: number,
): Promise<{ rows: PeakOffpeakRow[] }> {
  const res = await fetch(
    `${BASE}/${projectId}/charts/peak-offpeak?jour_type=${jourType}`,
    { headers: getAuthHeaders() },
  )
  if (!res.ok) throw new Error(`getPeakOffpeak failed: ${res.status}`)
  return res.json()
}
