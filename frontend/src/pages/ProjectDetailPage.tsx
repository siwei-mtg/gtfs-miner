import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ProgressPanel } from '@/components/organisms/ProgressPanel';
import { DownloadButton } from '@/components/organisms/DownloadButton';
import { ResultTable } from '@/components/organisms/ResultTable';
import { useProjectProgress } from '../hooks/useProjectProgress';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/atoms/button';
import { ChevronLeft } from 'lucide-react';
import { Badge } from '@/components/atoms/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

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

  const { messages, latestStatus } = useProjectProgress(id || null);

  const isCompleted = latestStatus === 'completed';

  if (!id) return <div>Invalid Project ID</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => navigate('/')} className="gap-2" aria-label="back-button">
          <ChevronLeft className="h-4 w-4" />
          Retour aux projets
        </Button>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold">Projet</h2>
          <Badge variant="outline" className="font-mono">{id}</Badge>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>État du traitement</CardTitle>
        </CardHeader>
        <CardContent>
          <ProgressPanel messages={messages} status={latestStatus} />
        </CardContent>
        {isCompleted && (
          <CardFooter className="justify-end border-t pt-4">
            <DownloadButton projectId={id} disabled={!isCompleted} />
          </CardFooter>
        )}
      </Card>

      {isCompleted && (
        <Card>
          <CardHeader>
            <CardTitle>Résultats</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="mb-4 flex flex-wrap h-auto gap-2 p-2">
                {RESULT_TABLES.map(table => (
                  <TabsTrigger key={table.id} value={table.id}>
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
      )}
    </div>
  );
};
