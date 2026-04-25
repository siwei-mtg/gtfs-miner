import { useState } from 'react'
import { Download } from 'lucide-react'
import { Button } from '@/components/atoms/button'
import { downloadGeoPackage } from '@/api/client'

interface GeoPackageDownloadButtonProps {
  projectId: string
  jourType: number
  disabled?: boolean
}

export function GeoPackageDownloadButton({
  projectId,
  jourType,
  disabled = false,
}: GeoPackageDownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const isDisabled = disabled || isDownloading

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={isDisabled}
      aria-label="download-geopackage-button"
      onClick={() => {
        setIsDownloading(true)
        downloadGeoPackage(projectId, jourType).finally(() => setIsDownloading(false))
      }}
      className="gap-2"
    >
      <Download className="h-4 w-4" />
      {isDownloading ? 'Téléchargement…' : 'Exporter GeoPackage'}
    </Button>
  )
}
