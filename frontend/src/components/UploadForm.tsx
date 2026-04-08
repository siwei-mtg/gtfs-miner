import { useState } from 'react'
import type { ProjectCreate } from '../types/api'

interface UploadFormProps {
  onSubmit: (file: File, params: ProjectCreate) => void
  isLoading?: boolean
  error?: string | null
}

const DEFAULT_PARAMS: ProjectCreate = {
  hpm_debut: '07:00',
  hpm_fin: '09:00',
  hps_debut: '17:00',
  hps_fin: '19:30',
  vacances: 'A',
  pays: '法国',
}

export function UploadForm({ onSubmit, isLoading = false, error = null }: UploadFormProps) {
  const [file, setFile] = useState<File | null>(null)
  const [params, setParams] = useState<ProjectCreate>(DEFAULT_PARAMS)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (file) onSubmit(file, params)
  }

  function handleParam(key: keyof ProjectCreate) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setParams((prev) => ({ ...prev, [key]: e.target.value }))
  }

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label htmlFor="gtfs-file">GTFS ZIP</label>
        <input
          id="gtfs-file"
          type="file"
          accept=".zip"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>

      <div>
        <label htmlFor="hpm_debut">HP matin début</label>
        <input id="hpm_debut" type="time" value={params.hpm_debut} onChange={handleParam('hpm_debut')} />
      </div>
      <div>
        <label htmlFor="hpm_fin">HP matin fin</label>
        <input id="hpm_fin" type="time" value={params.hpm_fin} onChange={handleParam('hpm_fin')} />
      </div>
      <div>
        <label htmlFor="hps_debut">HP soir début</label>
        <input id="hps_debut" type="time" value={params.hps_debut} onChange={handleParam('hps_debut')} />
      </div>
      <div>
        <label htmlFor="hps_fin">HP soir fin</label>
        <input id="hps_fin" type="time" value={params.hps_fin} onChange={handleParam('hps_fin')} />
      </div>
      <div>
        <label htmlFor="vacances">Vacances</label>
        <input id="vacances" type="text" value={params.vacances} onChange={handleParam('vacances')} />
      </div>
      <div>
        <label htmlFor="pays">Pays</label>
        <input id="pays" type="text" value={params.pays} onChange={handleParam('pays')} />
      </div>

      {error && <p role="alert">{error}</p>}

      <button type="submit" disabled={!file || isLoading}>
        {isLoading ? 'Traitement en cours…' : 'Lancer le traitement'}
      </button>
    </form>
  )
}
