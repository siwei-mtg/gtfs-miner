/**
 * DashboardPage — three-pane analytical dashboard (sidebar · map · right panel).
 *
 * The header's old jour_type dropdown has been retired: the two right-side
 * charts are now the interaction surface. Left sidebar opens any of the 15
 * result tables in a central popup that preserves filter state.
 */
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { downloadGeoPackage, downloadProjectResults, getJourTypes, type JourTypeOption } from '@/api/client'
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
import { DashboardSyncProvider, useDashboardSync } from '@/hooks/useDashboardSync'

export const DashboardPage: React.FC = () => {
  const { id: projectId } = useParams<{ id: string }>()
  const [jourTypeOptions, setJourTypeOptions] = useState<JourTypeOption[]>([])
  const [initialJourType, setInitialJourType] = useState<number | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
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

  if (!projectId) {
    return <div role="alert" className="p-8 text-destructive">Projet introuvable.</div>
  }
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
        />
      </DashboardSyncProvider>
    </ErrorBoundary>
  )
}

interface ShellProps {
  projectId: string
  jourTypeOptions: JourTypeOption[]
  bootError: string | null
}

function DashboardShell({ projectId, jourTypeOptions: _jourTypeOptions, bootError }: ShellProps) {
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
    <>
      <DashboardLayout
        header={
          <DashboardHeader
            projectId={projectId}
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
              <PassageAGLayer projectId={projectId} jourType={state.jourType} />
              <PassageArcLayer projectId={projectId} jourType={state.jourType} />
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
    </>
  )
}
