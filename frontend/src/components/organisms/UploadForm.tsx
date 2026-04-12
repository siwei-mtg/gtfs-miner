import { useState } from 'react'
import type { ProjectCreate } from '@/types/api'

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
  pays: 'france',
}

export function UploadForm({ onSubmit, isLoading = false, error = null }: UploadFormProps) {
  const [file, setFile] = useState<File | null>(null)
  const [params, setParams] = useState<ProjectCreate>(DEFAULT_PARAMS)
  const [validationError, setValidationError] = useState<string | null>(null)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setValidationError(null)

    if (params.hpm_fin <= params.hpm_debut) {
      setValidationError("La fin de l'heure de pointe du matin doit être postérieure au début.")
      return
    }
    if (params.hps_fin <= params.hps_debut) {
      setValidationError("La fin de l'heure de pointe du soir doit être postérieure au début.")
      return
    }

    if (file) onSubmit(file, params)
  }

  function handleParam(key: keyof ProjectCreate) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setParams((prev) => ({ ...prev, [key]: e.target.value }))
      setValidationError(null)
    }
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
        <input id="hpm_debut" type="time" value={params.hpm_debut} onChange={handleParam('hpm_debut')} required />
      </div>
      <div>
        <label htmlFor="hpm_fin">HP matin fin</label>
        <input id="hpm_fin" type="time" value={params.hpm_fin} onChange={handleParam('hpm_fin')} required />
      </div>
      <div>
        <label htmlFor="hps_debut">HP soir début</label>
        <input id="hps_debut" type="time" value={params.hps_debut} onChange={handleParam('hps_debut')} required />
      </div>
      <div>
        <label htmlFor="hps_fin">HP soir fin</label>
        <input id="hps_fin" type="time" value={params.hps_fin} onChange={handleParam('hps_fin')} required />
      </div>
      <div>
        <label htmlFor="vacances">Vacances</label>
        <select id="vacances" value={params.vacances} onChange={handleParam('vacances')}>
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="C">C</option>
          <option value="全部">全部</option>
        </select>
      </div>

      <input id="pays" type="hidden" value={params.pays} />

      {(error || validationError) && <p role="alert" className="error-message">{error || validationError}</p>}

      <button type="submit" disabled={!file || isLoading}>
        {isLoading ? 'Traitement en cours…' : 'Lancer le traitement'}
      </button>
    </form>
  )
}
