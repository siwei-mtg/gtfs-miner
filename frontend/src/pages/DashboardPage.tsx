/**
 * DashboardPage — single project surface.
 *
 * Routed at `/projects/:id`. The status feed (WebSocket via
 * `useProjectProgress`) decides which sub-view renders:
 *
 *   pending / uploading / processing / failed → ProjectProgressView
 *   completed                                  → 3-pane analytical dashboard
 *
 * The full progress journal stays accessible from the dashboard header even
 * after completion (Journal button in DashboardHeader).
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'

import {
  downloadGeoPackage,
  downloadProjectResults,
  getJourTypes,
  type JourTypeOption,
} from '@/api/client'
import { DashboardLayout } from '@/components/templates/DashboardLayout'
import { DashboardHeader } from '@/components/organisms/DashboardHeader'
import { DashboardRightPanel } from '@/components/organisms/DashboardRightPanel'
import { KpiRibbon } from '@/components/organisms/KpiRibbon'
import { MapView } from '@/components/organisms/MapView'
import { PassageAGLayer } from '@/components/PassageAGLayer'
import { PassageArcLayer } from '@/components/PassageArcLayer'
import { SIDEBAR_GROUPS, TableListSidebar } from '@/components/organisms/TableListSidebar'
import { TablePopup } from '@/components/organisms/TablePopup'
import { ErrorBoundary } from '@/components/molecules/ErrorBoundary'
import { ProgressPanel } from '@/components/organisms/ProgressPanel'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/atoms/button'
import { CodeTag } from '@/components/atoms/CodeTag'
import { Hairline } from '@/components/atoms/Hairline'
import { DashboardSyncProvider, useDashboardSync } from '@/hooks/useDashboardSync'
import { useProjectProgress } from '@/hooks/useProjectProgress'
import type { ProjectStatus, WebSocketMessage } from '@/types/api'

export const DashboardPage: React.FC = () => {
  const { id: projectId } = useParams<{ id: string }>()
  const { messages, latestStatus } = useProjectProgress(projectId ?? null)

  if (!projectId) {
    return <div role="alert" className="p-8 text-destructive">Projet introuvable.</div>
  }
  if (latestStatus === null) {
    return <div className="p-8 text-sm text-muted-foreground">Chargement…</div>
  }
  if (latestStatus !== 'completed') {
    return (
      <ProjectProgressView
        projectId={projectId}
        status={latestStatus}
        messages={messages}
      />
    )
  }
  return <CompletedDashboard projectId={projectId} progressMessages={messages} />
}

interface ProgressProps {
  projectId: string
  status: ProjectStatus
  messages: WebSocketMessage[]
}

function ProjectProgressView({ projectId, status, messages }: ProgressProps) {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-6 py-8">
      <div className="flex items-center gap-4 border-b border-hair pb-4">
        <Button
          asChild
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 text-ink-muted hover:text-ink"
        >
          <Link to="/" aria-label="back-button">
            <ChevronLeft className="h-4 w-4" /> Projets
          </Link>
        </Button>
        <Hairline orientation="vertical" className="h-5" />
        <h2 className="flex items-baseline gap-2 font-display text-2xl font-medium leading-none text-ink">
          Projet
          <CodeTag className="translate-y-[-1px] text-[13px]">{projectId}</CodeTag>
        </h2>
      </div>
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-[10px] font-medium uppercase tracking-[0.15em] text-ink-muted">
            État du traitement
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ProgressPanel messages={messages} status={status} />
        </CardContent>
      </Card>
    </div>
  )
}

interface CompletedProps {
  projectId: string
  progressMessages: WebSocketMessage[]
}

function CompletedDashboard({ projectId, progressMessages }: CompletedProps) {
  const [jourTypeOptions, setJourTypeOptions] = useState<JourTypeOption[]>([])
  const [initialJourType, setInitialJourType] = useState<number | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getJourTypes(projectId)
      .then((opts) => {
        if (cancelled) return
        setJourTypeOptions(opts)
        setInitialJourType(opts[0]?.value ?? 1)
      })
      .catch((err) => {
        if (cancelled) return
        console.error('Failed to load jour-types:', err)
        setBootError('Impossible de charger les types de jour pour ce projet.')
        setInitialJourType(1)
      })
    return () => { cancelled = true }
  }, [projectId])

  if (initialJourType === null) {
    return <div className="p-8 text-sm text-muted-foreground">Chargement…</div>
  }

  return (
    <ErrorBoundary scope="DashboardPage">
      <DashboardSyncProvider initialJourType={initialJourType}>
        <DashboardShell
          projectId={projectId}
          jourTypeOptions={jourTypeOptions}
          bootError={bootError}
          progressMessages={progressMessages}
        />
      </DashboardSyncProvider>
    </ErrorBoundary>
  )
}

interface ShellProps {
  projectId: string
  jourTypeOptions: JourTypeOption[]
  bootError: string | null
  progressMessages: WebSocketMessage[]
}

function DashboardShell({
  projectId,
  jourTypeOptions: _jourTypeOptions,
  bootError,
  progressMessages,
}: ShellProps) {
  const { state } = useDashboardSync()
  const [openTableId, setOpenTableId] = useState<string | null>(null)

  const tableIndex = useMemo(() => {
    const map = new Map<string, { code: string; name: string }>()
    for (const g of SIDEBAR_GROUPS) {
      for (const t of g.tables) map.set(t.id, { code: t.code, name: t.name })
    }
    return map
  }, [])

  const openLabel = openTableId ? tableIndex.get(openTableId) : undefined

  return (
    <DashboardLayout
      header={
        <DashboardHeader
          projectId={projectId}
          progressMessages={progressMessages}
          onExportGeoPackage={() => downloadGeoPackage(projectId, state.jourType)}
          onExportCsvZip={() => downloadProjectResults(projectId)}
        />
      }
      kpiRibbon={<KpiRibbon projectId={projectId} />}
      sidebar={
        <TableListSidebar
          activeTableId={openTableId}
          onTableClick={(id) => setOpenTableId(id)}
        />
      }
      map={
        <ErrorBoundary scope="Map pane">
          <MapView projectId={projectId} jourType={state.jourType}>
            <PassageAGLayer
              projectId={projectId}
              jourType={state.jourType}
              ligneIds={state.ligneIds}
              sousLigneKeys={state.sousLigneKeys}
            />
            <PassageArcLayer
              projectId={projectId}
              jourType={state.jourType}
              ligneIds={state.ligneIds}
              sousLigneKeys={state.sousLigneKeys}
            />
          </MapView>
        </ErrorBoundary>
      }
      rightPanel={
        <ErrorBoundary scope="Right panel">
          <DashboardRightPanel projectId={projectId} />
        </ErrorBoundary>
      }
      overlay={
        <>
          {bootError && (
            <div
              role="alert"
              className="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-md border bg-destructive/10 px-3 py-2 text-sm text-destructive shadow"
            >
              {bootError}
            </div>
          )}
          <TablePopup
            projectId={projectId}
            tableId={openTableId}
            tableLabel={openLabel ? `${openLabel.code} · ${openLabel.name}` : undefined}
            onClose={() => setOpenTableId(null)}
          />
        </>
      }
    />
  )
}
