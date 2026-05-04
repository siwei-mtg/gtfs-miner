import type {
  ColumnDistinctResponse,
  ColumnFilter,
  ProjectCreate,
  ProjectResponse,
  TableDataResponse,
  Token,
  UploadResponse,
  UserCreate,
  UserResponse,
} from '../types/api'

function normalizeOrigin(raw: string | undefined): string {
  if (!raw) return ''
  const s = raw.replace(/\/$/, '')
  return /^https?:\/\//.test(s) ? s : `https://${s}`
}
export const API_ORIGIN = normalizeOrigin(import.meta.env.VITE_API_URL as string | undefined)
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

export async function deleteProject(projectId: string): Promise<void> {
  const res = await fetch(`${BASE}/${projectId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`deleteProject failed: ${res.status}`)
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
  /** Task 38B: per-column filters (Excel-style header popovers).  AND-ed. */
  filters?: Record<string, ColumnFilter>
  /** Adds ``column_meta`` to the response (cheap, single bounded distinct
   *  query per non-numeric column).  Front-end only needs this once per
   *  table mount to pick the popover layout. */
  column_meta?: boolean
}

/** Encode one ColumnFilter into the ``op:rest`` payload accepted by the
 *  backend.  Returns null when the filter is empty so callers skip the
 *  query-string entry. */
function encodeColumnFilter(f: ColumnFilter): string | null {
  if (f.kind === 'in') {
    if (f.values.length === 0) return null
    return `in:${f.values.join(',')}`
  }
  if (f.kind === 'range') {
    if (f.min === undefined && f.max === undefined) return null
    return `range:${f.min ?? ''}:${f.max ?? ''}`
  }
  if (f.kind === 'contains') {
    if (!f.term) return null
    return `contains:${f.term}`
  }
  return null
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
  if (params.filters) {
    for (const [col, filter] of Object.entries(params.filters)) {
      const encoded = encodeColumnFilter(filter)
      if (encoded !== null) query.append(`filter[${col}]`, encoded)
    }
  }
  if (params.column_meta) query.append('column_meta', 'true')

  const res = await fetch(`${BASE}/${projectId}/tables/${tableName}?${query.toString()}`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`getTableData failed: ${res.status}`)
  return res.json()
}

export interface ResolveResponse {
  ligne_ids: number[]
  route_types: string[]
  ag_ids: number[]
}

/** Translate per-table column filters into canonical ligne_ids / route_types
 *  the rest of the dashboard (map, KPI, charts) consumes.  Empty lists are
 *  returned for canonical columns the source table doesn't have. */
export async function resolveTableFilters(
  projectId: string,
  tableName: string,
  filters: Record<string, ColumnFilter>,
): Promise<ResolveResponse> {
  const query = new URLSearchParams()
  for (const [col, filter] of Object.entries(filters)) {
    const encoded = encodeColumnFilter(filter)
    if (encoded !== null) query.append(`filter[${col}]`, encoded)
  }
  const url = `${BASE}/${projectId}/tables/${tableName}/resolve?${query.toString()}`
  const res = await fetch(url, { headers: getAuthHeaders() })
  if (!res.ok) throw new Error(`resolveTableFilters failed: ${res.status}`)
  return res.json()
}

export async function getColumnDistinct(
  projectId: string,
  tableName: string,
  column: string,
  opts: { q?: string; limit?: number } = {},
): Promise<ColumnDistinctResponse> {
  const query = new URLSearchParams()
  if (opts.q) query.append('q', opts.q)
  if (opts.limit !== undefined) query.append('limit', opts.limit.toString())
  const url =
    `${BASE}/${projectId}/tables/${tableName}/columns/${encodeURIComponent(column)}/distinct` +
    (query.toString() ? `?${query}` : '')
  const res = await fetch(url, { headers: getAuthHeaders() })
  if (!res.ok) throw new Error(`getColumnDistinct failed: ${res.status}`)
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

/**
 * @deprecated Replaced by `getCoursesByHour`. Scheduled for removal one
 * release after the dashboard refonte lands.
 */
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

export interface CoursesByJourTypeRow {
  jour_type: number
  jour_type_name: string
  nb_courses: number
}

export async function getCoursesByJourType(
  projectId: string,
): Promise<{ rows: CoursesByJourTypeRow[] }> {
  const res = await fetch(
    `${BASE}/${projectId}/charts/courses-by-jour-type`,
    { headers: getAuthHeaders() },
  )
  if (!res.ok) throw new Error(`getCoursesByJourType failed: ${res.status}`)
  return res.json()
}

export interface CoursesByHourRow {
  heure: number
  nb_courses: number
}

function appendRouteTypes(query: URLSearchParams, routeTypes?: string[]): void {
  if (!routeTypes || routeTypes.length === 0) return
  for (const rt of routeTypes) query.append('route_types', rt)
}

function appendIntList(
  query: URLSearchParams,
  param: string,
  values?: number[],
): void {
  if (!values || values.length === 0) return
  for (const v of values) query.append(param, String(v))
}

/** Optional cross-pane context that narrows KPIs / charts the same way the
 *  map and tables already filter.  Mirrors the backend query params one-to-one
 *  (route_types repeats, ligne_ids repeats, id_ag_num repeats).  Pass omitted
 *  fields when no filter is active so the response equals the "base" total.
 */
export interface FilterContext {
  routeTypes?: string[]
  ligneIds?: number[]
  agIds?: number[]
}

function appendFilterContext(query: URLSearchParams, ctx?: FilterContext): void {
  if (!ctx) return
  appendRouteTypes(query, ctx.routeTypes)
  appendIntList(query, 'ligne_ids', ctx.ligneIds)
  appendIntList(query, 'id_ag_num', ctx.agIds)
}

export async function getCoursesByHour(
  projectId: string,
  jourType: number,
  ctx?: FilterContext,
): Promise<{ rows: CoursesByHourRow[] }> {
  const query = new URLSearchParams({ jour_type: String(jourType) })
  appendFilterContext(query, ctx)
  const res = await fetch(
    `${BASE}/${projectId}/charts/courses-by-hour?${query.toString()}`,
    { headers: getAuthHeaders() },
  )
  if (!res.ok) throw new Error(`getCoursesByHour failed: ${res.status}`)
  return res.json()
}

export interface KpiResponse {
  nb_lignes: number
  nb_arrets: number
  nb_courses: number
  kcc_total: number
}

export async function getKpis(
  projectId: string,
  jourType: number,
  ctx?: FilterContext,
): Promise<KpiResponse> {
  const query = new URLSearchParams({ jour_type: String(jourType) })
  appendFilterContext(query, ctx)
  const res = await fetch(
    `${BASE}/${projectId}/kpis?${query.toString()}`,
    { headers: getAuthHeaders() },
  )
  if (!res.ok) throw new Error(`getKpis failed: ${res.status}`)
  return res.json()
}
