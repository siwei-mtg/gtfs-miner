import React, { useEffect, useState } from 'react';
import { getTableData, downloadTableCsv } from '@/api/client';
import type { TableDataResponse } from '@/types/api';

interface ResultTableProps {
  projectId: string;
  tableName: string;
}

export const ResultTable: React.FC<ResultTableProps> = ({ projectId, tableName }) => {
  const [data, setData] = useState<TableDataResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(50);
  const [sortBy, setSortBy] = useState<string | undefined>(undefined);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  useEffect(() => {
    let mounted = true;
    setIsLoading(true);

    getTableData(projectId, tableName, {
      skip,
      limit,
      sort_by: sortBy,
      sort_order: sortOrder,
    })
      .then(res => {
        if (mounted) {
          setData(res);
          setError(null);
        }
      })
      .catch(err => {
        if (mounted) setError('Failed to load table data');
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });

    return () => { mounted = false; };
  }, [projectId, tableName, skip, limit, sortBy, sortOrder]);

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortOrder('asc');
    }
    setSkip(0);
  };

  return (
    <div className="result-table-container">
      <div className="controls">
        <button
          className="download-button"
          disabled={isDownloading}
          onClick={() => {
            setIsDownloading(true);
            downloadTableCsv(projectId, tableName).finally(() => setIsDownloading(false));
          }}
        >
          {isDownloading ? 'Téléchargement…' : 'Download CSV'}
        </button>

        <div className="pagination-controls">
          <select 
            value={limit} 
            onChange={e => {
              setLimit(Number(e.target.value));
              setSkip(0);
            }}
            aria-label="Rows per page"
          >
            <option value={50}>50 rows</option>
            <option value={100}>100 rows</option>
            <option value={200}>200 rows</option>
          </select>
        </div>
      </div>

      {isLoading && <div className="skeleton-loader" aria-busy="true">Loading table data...</div>}
      {error && <div role="alert" className="error">{error}</div>}

      {!isLoading && !error && data && (
        <>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  {data.columns.map(col => (
                    <th key={col} onClick={() => handleSort(col)} style={{ cursor: 'pointer' }}>
                      {col} {sortBy === col ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, idx) => (
                  <tr key={idx}>
                    {data.columns.map(col => (
                      <td key={col}>{row[col]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-footer">
            <span>Total rows: {data.total}</span>
            <div className="page-navigation">
              <button 
                onClick={() => setSkip(Math.max(0, skip - limit))}
                disabled={skip === 0}
              >
                Previous
              </button>
              <button 
                onClick={() => setSkip(skip + limit)}
                disabled={skip + limit >= data.total}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
