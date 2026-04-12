import type { ProjectStatus, WebSocketMessage } from '@/types/api'

interface ProgressPanelProps {
  messages: WebSocketMessage[]
  status?: ProjectStatus | null
}

const STEP_LABELS = [
  '读取与解压 GTFS 文件',
  '标准化 GTFS 表',
  '空间聚类生成站点映射',
  '生成行程、弧段与班次数据',
  '生成线路与子线路',
  '生成服务日期与日类型',
  '计算通过次数与 KCC 指标',
]

function getStepIndex(step: string): number {
  const match = step.match(/^\[(\d)\/7\]/)
  return match ? parseInt(match[1], 10) - 1 : -1
}

export function ProgressPanel({ messages, status }: ProgressPanelProps) {
  if (messages.length === 0) {
    const label =
      status === 'completed' ? 'Traitement terminé.' :
      status === 'failed'    ? 'Traitement échoué.' :
                               'En attente du démarrage…'
    return (
      <div aria-label="progress-panel">
        <p>{label}</p>
      </div>
    )
  }

  const latest = messages[messages.length - 1]
  const completedSteps = new Set(
    messages.map((m) => getStepIndex(m.step)).filter((i) => i >= 0)
  )

  return (
    <div aria-label="progress-panel">
      <ol>
        {STEP_LABELS.map((label, i) => {
          const done = completedSteps.has(i)
          const matchedMsg = messages.find((m) => getStepIndex(m.step) === i)
          return (
            <li key={i} aria-label={`step-${i + 1}`}>
              <span aria-hidden>{done ? '✓' : '○'}</span>{' '}
              {matchedMsg ? matchedMsg.step : label}
            </li>
          )
        })}
      </ol>

      <p aria-label="elapsed-time">Temps écoulé : {latest.time_elapsed} s</p>

      <p aria-label="status">
        Statut :{' '}
        {latest.status === 'completed' && <span>Terminé</span>}
        {latest.status === 'failed' && <span role="alert">Échec — {latest.error}</span>}
        {latest.status === 'processing' && <span>En cours…</span>}
      </p>
    </div>
  )
}
