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

export interface TableDataResponse {
  total: number
  rows: Record<string, any>[]
  columns: string[]
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
