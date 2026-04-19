/**
 * DashboardPage — three-pane analytics view (Map + Charts + Table) with
 * filter state shared via <DashboardSyncProvider> (Task 39B).
 *
 *     ┌──────────────┬──────────────┐
 *     │              │  Charts      │
 *     │   Map        ├──────────────┤
 *     │              │  ResultTable │
 *     └──────────────┴──────────────┘
 *
 * - Map pie-click  → TOGGLE_AG_ID       → Charts + Table re-query
 * - Chart click    → TOGGLE_ROUTE_TYPE  → Map + Table re-query
 * - Table filter   → SET_ROUTE_TYPES    → Map + Charts re-query
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { getJourTypes, type JourTypeOption } from '@/api/client';
import { Button } from '@/components/atoms/button';
import { DashboardCharts } from '@/components/organisms/DashboardCharts';
import { MapView } from '@/components/organisms/MapView';
import { PassageAGLayer } from '@/components/PassageAGLayer';
import { PassageArcLayer } from '@/components/PassageArcLayer';
import { ResultTable } from '@/components/organisms/ResultTable';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  DashboardSyncProvider,
  useDashboardSync,
} from '@/hooks/useDashboardSync';

const RESULT_TABLES: Array<{ id: string; label: string }> = [
  { id: 'a1', label: 'A1: AG' },
  { id: 'b1', label: 'B1: Lignes' },
  { id: 'b2', label: 'B2: Sous-Lignes' },
  { id: 'e1', label: 'E1: Passage AG' },
  { id: 'e4', label: 'E4: Passage Arc' },
  { id: 'f1', label: 'F1: Courses' },
  { id: 'f3', label: 'F3: KCC' },
];

export const DashboardPage: React.FC = () => {
  const { id: projectId } = useParams<{ id: string }>();
  const [jourTypeOptions, setJourTypeOptions] = useState<JourTypeOption[]>([]);
  const [initialJourType, setInitialJourType] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    getJourTypes(projectId)
      .then((opts) => {
        if (cancelled) return;
        setJourTypeOptions(opts);
        setInitialJourType(opts[0]?.value ?? 1);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('Failed to load jour-types:', err);
        setError('Impossible de charger les types de jour pour ce projet.');
        setInitialJourType(1);
      });
    return () => { cancelled = true; };
  }, [projectId]);

  if (!projectId) {
    return <div role="alert" className="p-8 text-destructive">Projet introuvable.</div>;
  }
  if (initialJourType === null) {
    return <div className="p-8 text-sm text-muted-foreground">Chargement…</div>;
  }

  return (
    <DashboardSyncProvider initialJourType={initialJourType}>
      <DashboardShell
        projectId={projectId}
        jourTypeOptions={jourTypeOptions}
        bootError={error}
      />
    </DashboardSyncProvider>
  );
};

interface ShellProps {
  projectId: string;
  jourTypeOptions: JourTypeOption[];
  bootError: string | null;
}

function DashboardShell({ projectId, jourTypeOptions, bootError }: ShellProps) {
  const { state, dispatch } = useDashboardSync();
  const [activeTable, setActiveTable] = useState<string>('b1');

  const routeTypesForTable = useMemo(
    () => (activeTable === 'b1' ? state.routeTypes : undefined),
    [activeTable, state.routeTypes],
  );

  return (
    <div className="flex flex-col gap-4" data-testid="dashboard-page">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link to={`/projects/${projectId}`}>← Retour</Link>
          </Button>
          <h1 className="text-lg font-semibold">Tableau de bord</h1>
          <span className="text-xs text-muted-foreground">{projectId}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">Type de jour</span>
          <Select
            value={String(state.jourType)}
            onValueChange={(v) => dispatch({ type: 'SET_JOUR_TYPE', payload: Number(v) })}
          >
            <SelectTrigger className="w-48" aria-label="jour-type-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {jourTypeOptions.map((opt) => (
                <SelectItem key={opt.value} value={String(opt.value)}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {(state.routeTypes.length > 0 || state.agIds.length > 0) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => dispatch({ type: 'CLEAR_FILTERS' })}
            >
              Effacer les filtres
            </Button>
          )}
        </div>
      </div>

      {bootError && (
        <div role="alert" className="text-sm text-destructive">{bootError}</div>
      )}

      <div className="grid gap-4 xl:grid-cols-2 xl:grid-rows-[minmax(0,1fr)_minmax(0,1fr)] xl:h-[calc(100vh-10rem)]">
        {/* Map pane (spans both rows on xl) */}
        <section
          data-testid="dashboard-map"
          className="xl:row-span-2 min-h-[400px] rounded-lg border overflow-hidden"
        >
          <MapView
            projectId={projectId}
            jourType={state.jourType}
            onStopClick={(agId, shiftKey) =>
              dispatch({ type: 'TOGGLE_AG_ID', payload: agId, shift: shiftKey })
            }
          >
            <PassageAGLayer projectId={projectId} jourType={state.jourType} />
            <PassageArcLayer projectId={projectId} jourType={state.jourType} />
          </MapView>
        </section>

        {/* Charts pane */}
        <section
          data-testid="dashboard-charts"
          className="rounded-lg border p-3 overflow-auto"
        >
          <DashboardCharts
            projectId={projectId}
            jourType={state.jourType}
            filters={state}
            onRouteTypeClick={(rt) => dispatch({ type: 'TOGGLE_ROUTE_TYPE', payload: rt })}
          />
        </section>

        {/* Table pane (with tabs) */}
        <section
          data-testid="dashboard-table"
          className="rounded-lg border p-3 overflow-auto"
        >
          <Tabs value={activeTable} onValueChange={setActiveTable}>
            <TabsList className="flex-wrap h-auto">
              {RESULT_TABLES.map((t) => (
                <TabsTrigger key={t.id} value={t.id}>{t.label}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <div className="mt-3">
            <ResultTable
              projectId={projectId}
              tableName={activeTable}
              externalEnumValues={routeTypesForTable}
              onFilterChange={(f) => {
                if (f.routeTypes !== undefined) {
                  dispatch({ type: 'SET_ROUTE_TYPES', payload: f.routeTypes });
                }
              }}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
