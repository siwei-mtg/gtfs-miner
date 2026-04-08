import { getDownloadUrl } from '../api/client'

interface DownloadButtonProps {
  projectId: string | null
  disabled?: boolean
}

export function DownloadButton({ projectId, disabled = false }: DownloadButtonProps) {
  const isDisabled = disabled || !projectId

  if (isDisabled) {
    return (
      <button disabled aria-label="download-button">
        Télécharger les résultats
      </button>
    )
  }

  return (
    <a
      href={getDownloadUrl(projectId)}
      download
      role="button"
      aria-label="download-button"
    >
      Télécharger les résultats
    </a>
  )
}
