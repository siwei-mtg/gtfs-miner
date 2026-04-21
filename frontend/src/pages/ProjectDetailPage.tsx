import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ProgressPanel } from '@/components/organisms/ProgressPanel';
import { DownloadButton } from '@/components/organisms/DownloadButton';
import { GeoPackageDownloadButton } from '@/components/organisms/GeoPackageDownloadButton';
import { ResultTable } from '@/components/organisms/ResultTable';
import { MapView } from '@/components/organisms/MapView';
import { PassageAGLayer } from '@/components/PassageAGLayer';
import { PassageArcLayer } from '@/components/PassageArcLayer';
import { useProjectProgress } from '../hooks/useProjectProgress';
import { getJourTypes, type JourTypeOption } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/atoms/button';
import { ChevronLeft, Map as MapIcon, Table as TableIcon, LayoutDashboard } from 'lucide-react';
import { CodeTag } from '@/components/atoms/CodeTag';
import { Hairline } from '@/components/atoms/Hairline';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const RESULT_TABLES = [
  { id: 'a1', label: 'A1: Arrêts Génériques' },
  { id: 'a2', label: 'A2: Arrêts Physiques' },
  { id: 'b1', label: 'B1: Lignes' },
  { id: 'b2', label: 'B2: Sous-Lignes' },
  { id: 'c1', label: 'C1: Courses' },
  { id: 'c2', label: 'C2: Itinéraire' },
  { id: 'c3', label: 'C3: Itinéraire Arc' },
  { id: 'd1', label: 'D1: Service Dates' },
  { id: 'd2', label: 'D2: Service Jourtype' },
  { id: 'e1', label: 'E1: Passage AG' },
  { id: 'e4', label: 'E4: Passage Arc' },
  { id: 'f1', label: 'F1: Courses/Lignes' },
  { id: 'f2', label: 'F2: Caract. Sous-Lignes' },
  { id: 'f3', label: 'F3: KCC Lignes' },
  { id: 'f4', label: 'F4: KCC Sous-Lignes' },
];

export const ProjectDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(RESULT_TABLES[0].id);
  const [viewMode, setViewMode] = useState<'map' | 'table'>('table');
  const [jourType, setJourType] = useState<number>(1);
  const [jourTypeOptions, setJourTypeOptions] = useState<JourTypeOption[]>([]);

  const { messages, latestStatus } = useProjectProgress(id || null);

  const isCompleted = latestStatus === 'completed';

  useEffect(() => {
    if (!id || !isCompleted) return;
    getJourTypes(id)
      .then((opts) => {
        setJourTypeOptions(opts);
        if (opts.length && !opts.some((o) => o.value === jourType)) {
          setJourType(opts[0].value);
        }
      })
      .catch((err) => console.error('Failed to load jour-types:', err));
    // Only refetch when the project identity or completion state flips —
    // keeping the current jourType across reloads is intentional.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isCompleted]);

  if (!id) return <div>Invalid Project ID</div>;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-6 py-6">
      {/* Header éditorial */}
      <div className="flex items-center justify-between border-b border-hair pb-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/')}
            className="h-8 gap-1.5 px-2 text-ink-muted hover:text-ink"
            aria-label="back-button"
          >
            <ChevronLeft className="h-4 w-4" />
            Projets
          </Button>
          <Hairline orientation="vertical" className="h-5" />
          <h2 className="flex items-baseline gap-2 font-display text-2xl font-medium leading-none text-ink">
            Projet
            <CodeTag className="translate-y-[-1px] text-[13px]">{id}</CodeTag>
          </h2>
        </div>
        {isCompleted && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 bg-muted p-1 rounded-lg">
              <Button
                variant={viewMode === 'table' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('table')}
                className="gap-2"
              >
                <TableIcon className="h-4 w-4" />
                Tableaux
              </Button>
              <Button
                variant={viewMode === 'map' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('map')}
                className="gap-2"
              >
                <MapIcon className="h-4 w-4" />
                Carte
              </Button>
            </div>
            <Button
              variant="default"
              size="sm"
              onClick={() => navigate(`/projects/${id}/dashboard`)}
              className="gap-2"
              aria-label="open-dashboard"
            >
              <LayoutDashboard className="h-4 w-4" />
              Tableau de bord
            </Button>
          </div>
        )}
      </div>

      {/* Progress Section */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-[10px] font-medium uppercase tracking-[0.15em] text-ink-muted">
            État du traitement
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ProgressPanel messages={messages} status={latestStatus} />
        </CardContent>
        {isCompleted && (
          <CardFooter className="justify-end border-t py-3">
            <DownloadButton projectId={id} disabled={!isCompleted} />
          </CardFooter>
        )}
      </Card>

      {/* Content Section */}
      {isCompleted && (
        <>
          {viewMode === 'map' ? (
            <Card className="overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3 border-b bg-muted/30">
                <label htmlFor="jour-type-select" className="text-sm font-medium">
                  Jour type :
                </label>
                <Select
                  value={String(jourType)}
                  onValueChange={(v) => setJourType(Number(v))}
                  disabled={jourTypeOptions.length === 0}
                >
                  <SelectTrigger id="jour-type-select" className="w-60">
                    <SelectValue placeholder="Chargement..." />
                  </SelectTrigger>
                  <SelectContent>
                    {jourTypeOptions.map((o) => (
                      <SelectItem key={o.value} value={String(o.value)}>
                        {o.value} – {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="ml-auto">
                  <GeoPackageDownloadButton
                    projectId={id}
                    jourType={jourType}
                    disabled={jourTypeOptions.length === 0}
                  />
                </div>
              </div>
              <CardContent className="p-0">
                <div className="h-[600px] w-full relative">
                  <MapView projectId={id} jourType={jourType}>
                    <PassageAGLayer projectId={id} jourType={jourType} />
                    <PassageArcLayer projectId={id} jourType={jourType} />
                  </MapView>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                  <TabsList className="mb-4 flex flex-wrap h-auto gap-2 p-1 bg-muted/50">
                    {RESULT_TABLES.map(table => (
                      <TabsTrigger key={table.id} value={table.id} className="text-xs">
                        {table.label.split(':')[0]}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  {RESULT_TABLES.map(table => (
                    <TabsContent key={table.id} value={table.id}>
                       <ResultTable projectId={id} tableName={table.id} />
                    </TabsContent>
                  ))}
                </Tabs>
              </CardContent>
            </Card>
          ) }
        </>
      )}
    </div>
  );
};
