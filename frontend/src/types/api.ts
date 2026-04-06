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
