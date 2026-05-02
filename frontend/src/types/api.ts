export type ProjectStatus = 'pending' | 'uploading' | 'processing' | 'completed' | 'failed'

export interface ProjectCreate {
  hpm_debut: string
  hpm_fin: string
  hps_debut: string
  hps_fin: string
  vacances: string
  pays: string
}

export interface ProjectResponse {
  id: string
  status: ProjectStatus
  created_at: string
  updated_at: string
  parameters: ProjectCreate
  error_message: string | null
  reseau: string | null
  validite_debut: number | null
  validite_fin: number | null
}

export interface WebSocketMessage {
  project_id: string
  status: ProjectStatus
  step: string
  time_elapsed: number
  error: string | null
}

export interface UploadResponse {
  msg: string
  project_id: string
}

export type ColumnDataType = 'enum' | 'numeric' | 'text'

export interface ColumnMeta {
  type: ColumnDataType
  total_distinct: number
}

export interface TableDataResponse {
  total: number
  rows: Record<string, any>[]
  columns: string[]
  /** Present only when the request asked for it (?column_meta=true).  Powers
   *  the per-header Excel-style filter popover layout (Task 38B). */
  column_meta?: Record<string, ColumnMeta>
}

/** UI-side per-column filter shape — the column is keyed by the parent
 *  Map<col, ColumnFilter>, so it does not appear in this discriminated union. */
export type ColumnFilter =
  | { kind: 'in'; values: string[] }
  | { kind: 'range'; min?: number; max?: number }
  | { kind: 'contains'; term: string }

export interface DistinctValue {
  value: string | number | null
  count: number
}

export interface ColumnDistinctResponse {
  values: DistinctValue[]
  total_distinct: number
  truncated: boolean
}

export interface UserCreate {
  email: string
  password: string
  tenant_name: string
}

export type Plan = 'free' | 'pro' | 'enterprise'

export interface UserResponse {
  id: string
  email: string
  role: string
  tenant_id: string
  plan: Plan
  created_at: string
}

export interface Token {
  access_token: string
  token_type: string
}

export interface TenantCreate {
  name: string
}
