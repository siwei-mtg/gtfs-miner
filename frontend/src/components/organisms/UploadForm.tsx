import { useState, useRef } from 'react'
import type { ProjectCreate } from '@/types/api'
import { Button } from '@/components/atoms/button'
import { Input } from '@/components/atoms/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { UploadCloud, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

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
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0])
    }
  }
  
  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0])
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div
        className={cn(
          "border-2 border-dashed rounded-lg p-8 flex flex-col items-center justify-center transition-colors cursor-pointer",
          isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:bg-muted/50"
        )}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={(e) => { e.preventDefault(); setIsDragging(false) }}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          id="gtfs-file"
          type="file"
          accept=".zip"
          className="hidden"
          onChange={handleFileChange}
          ref={fileInputRef}
          aria-label="GTFS ZIP"
        />
        <UploadCloud className="h-10 w-10 text-muted-foreground mb-4" />
        {file ? (
          <p className="text-sm font-medium text-primary">{file.name}</p>
        ) : (
          <div className="text-center">
            <p className="text-sm font-medium">Cliquez ou glissez un fichier GTFS ZIP ici</p>
            <p className="text-sm text-muted-foreground mt-1">Taille max recommandée : 500 MB</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label htmlFor="hpm_debut" className="text-sm font-medium leading-none">HP matin début</label>
          <Input id="hpm_debut" type="time" value={params.hpm_debut} onChange={(e) => setParams(p => ({ ...p, hpm_debut: e.target.value }))} required />
        </div>
        <div className="space-y-2">
          <label htmlFor="hpm_fin" className="text-sm font-medium leading-none">HP matin fin</label>
          <Input id="hpm_fin" type="time" value={params.hpm_fin} onChange={(e) => setParams(p => ({ ...p, hpm_fin: e.target.value }))} required />
        </div>
        <div className="space-y-2">
          <label htmlFor="hps_debut" className="text-sm font-medium leading-none">HP soir début</label>
          <Input id="hps_debut" type="time" value={params.hps_debut} onChange={(e) => setParams(p => ({ ...p, hps_debut: e.target.value }))} required />
        </div>
        <div className="space-y-2">
          <label htmlFor="hps_fin" className="text-sm font-medium leading-none">HP soir fin</label>
          <Input id="hps_fin" type="time" value={params.hps_fin} onChange={(e) => setParams(p => ({ ...p, hps_fin: e.target.value }))} required />
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="vacances" className="text-sm font-medium leading-none">Vacances</label>
        <Select value={params.vacances} onValueChange={(val) => setParams(p => ({...p, vacances: val}))} name="vacances">
          <SelectTrigger id="vacances" aria-label="Vacances">
            <SelectValue placeholder="Sélectionner le type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="A">A</SelectItem>
            <SelectItem value="B">B</SelectItem>
            <SelectItem value="C">C</SelectItem>
            <SelectItem value="全部">全部</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <input id="pays" type="hidden" value={params.pays} />

      {(error || validationError) && (
        <Alert variant="destructive">
          <AlertDescription>{error || validationError}</AlertDescription>
        </Alert>
      )}

      <Button type="submit" disabled={!file || isLoading} className="w-full">
        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {isLoading ? 'Traitement en cours…' : 'Lancer le traitement'}
      </Button>
    </form>
  )
}
