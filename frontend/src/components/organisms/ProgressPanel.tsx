import type { ProjectStatus, WebSocketMessage } from '@/types/api'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/atoms/badge'
import { Check, Circle, Loader2 } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface ProgressPanelProps {
  messages: WebSocketMessage[]
  status?: ProjectStatus | null
}

const STEP_LABELS = [
  'Lecture et décompression du fichier GTFS',
  'Normalisation des tables GTFS',
  'Clustering spatial et cartographie des arrêts',
  'Génération des itinéraires, arcs et courses',
  'Génération des lignes et sous-lignes',
  'Génération des dates de service et types de jour',
  'Calcul des nombres de passages et indicateurs KCC',
  'Écriture des résultats en base de données',
  'Construction de la base de requêtes (DWD)',
]

function getStepIndex(step: string): number {
  const match = step.match(/^\[(\d+)\/(\d+)\]/)
  return match ? parseInt(match[1], 10) - 1 : -1
}

export function ProgressPanel({ messages, status }: ProgressPanelProps) {
  if (messages.length === 0) {
    const label =
      status === 'completed' ? 'Traitement terminé.' :
      status === 'failed'    ? 'Traitement échoué.' :
                               'En attente du démarrage…'
    return (
      <div aria-label="progress-panel" className="py-4">
        <p className="text-muted-foreground">{label}</p>
      </div>
    )
  }

  const latest = messages[messages.length - 1]
  const completedSteps = new Set(
    messages.map((m) => getStepIndex(m.step)).filter((i) => i >= 0)
  )

  const currentStepMsg = latest.status === 'processing' ? getStepIndex(latest.step) : -1

  const computed = Math.round((completedSteps.size / STEP_LABELS.length) * 100)
  const progressPercentage = status === 'completed' ? 100 : Math.min(99, computed)

  return (
    <div aria-label="progress-panel" className="space-y-6">
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="font-medium text-foreground">Progression</span>
          <span className="text-muted-foreground">{progressPercentage}%</span>
        </div>
        <Progress value={progressPercentage} className="h-2" />
      </div>

      <ol className="space-y-3">
        {STEP_LABELS.map((label, i) => {
          const done = completedSteps.has(i) || (status === 'completed' && i < STEP_LABELS.length)
          const isCurrent = currentStepMsg === i && status !== 'completed'
          const matchedMsg = messages.find((m) => getStepIndex(m.step) === i)
          return (
            <li key={i} aria-label={`step-${i + 1}`} className="flex items-center gap-3 text-sm">
              <span aria-hidden={false} className="flex-shrink-0">
                {done ? (
                  <>
                    <span className="sr-only">✓</span>
                    <Check className="h-4 w-4 text-green-500" />
                  </>
                ) : isCurrent ? (
                  <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
                ) : (
                  <>
                    <span className="sr-only">○</span>
                    <Circle className="h-4 w-4 text-muted-foreground" />
                  </>
                )}
              </span>
              <span className={done ? 'text-foreground' : isCurrent ? 'text-foreground font-medium' : 'text-muted-foreground'}>
                {matchedMsg ? matchedMsg.step : label}
              </span>
            </li>
          )
        })}
      </ol>

      <div className="flex items-center gap-2 text-sm text-muted-foreground pt-2">
        <Badge variant="secondary" aria-label="elapsed-time">Temps écoulé : {latest.time_elapsed} s</Badge>
        <div aria-label="status" className="flex items-center gap-2">
          <span>Statut :</span>
          {latest.status === 'completed' && <strong className="text-green-600">Terminé</strong>}
          {latest.status === 'processing' && <strong className="text-blue-600">En cours…</strong>}
        </div>
      </div>
      
      {latest.status === 'failed' && (
        <Alert variant="destructive" role="alert" className="mt-4">
          <AlertDescription>Échec — {latest.error}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}
