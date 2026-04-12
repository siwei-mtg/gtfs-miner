import { useState } from 'react'
import { downloadProjectResults } from '@/api/client'

interface DownloadButtonProps {
  projectId: string | null
  disabled?: boolean
}

export function DownloadButton({ projectId, disabled = false }: DownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const isDisabled = disabled || !projectId || isDownloading

  return (
    <button
      disabled={isDisabled}
      aria-label="download-button"
      onClick={() => {
        if (!projectId) return
        setIsDownloading(true)
        downloadProjectResults(projectId).finally(() => setIsDownloading(false))
      }}
    >
      {isDownloading ? 'Téléchargement…' : 'Télécharger les résultats'}
    </button>
  )
}
