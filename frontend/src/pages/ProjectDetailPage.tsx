import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ProgressPanel } from '@/components/organisms/ProgressPanel';
import { DownloadButton } from '@/components/organisms/DownloadButton';
import { ResultTable } from '@/components/organisms/ResultTable';
import { useProjectProgress } from '../hooks/useProjectProgress';

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
  const isFailed = latestStatus === 'failed';

  if (!id) return <div>Invalid Project ID</div>;

  return (
    <div className="project-detail-container">
      <div className="header">
        <button onClick={() => navigate('/')}>&larr; Back to Projects</button>
        <h2>Project {id}</h2>
      </div>

      <ProgressPanel messages={messages} status={latestStatus} />
      
      <div className="actions">
        <DownloadButton
          projectId={isCompleted ? id : null}
          disabled={!isCompleted}
        />
      </div>

      {isCompleted && (
        <div className="results-section">
          <h3>Results</h3>
          <div className="tabs">
            {RESULT_TABLES.map(table => (
              <button 
                key={table.id}
                className={activeTab === table.id ? 'active' : ''}
                onClick={() => setActiveTab(table.id)}
              >
                {table.label}
              </button>
            ))}
          </div>
          <div className="tab-content">
             <ResultTable projectId={id} tableName={activeTab} />
          </div>
        </div>
      )}
    </div>
  );
};
