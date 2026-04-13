import React, { useEffect, useState } from 'react';
import { getTableData, downloadTableCsv } from '@/api/client';
import type { TableDataResponse } from '@/types/api';
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '@/components/ui/table';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Pagination, PaginationContent, PaginationItem,
  PaginationPrevious, PaginationNext,
} from '@/components/ui/pagination';
import { Button } from '@/components/atoms/button';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

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
      .catch(() => {
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

  const isPrevDisabled = skip === 0;
  const isNextDisabled = data ? skip + limit >= data.total : true;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          disabled={isDownloading}
          onClick={() => {
            setIsDownloading(true);
            downloadTableCsv(projectId, tableName).finally(() => setIsDownloading(false));
          }}
        >
          {isDownloading ? 'Téléchargement…' : 'Download CSV'}
        </Button>

        <Select
          name="rows-per-page"
          value={String(limit)}
          onValueChange={(val) => {
            setLimit(Number(val));
            setSkip(0);
          }}
        >
          <SelectTrigger className="w-32" aria-label="Rows per page">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="50">50 rows</SelectItem>
            <SelectItem value="100">100 rows</SelectItem>
            <SelectItem value="200">200 rows</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading && (
        <div className="text-sm text-muted-foreground" aria-busy="true">
          Loading table data...
        </div>
      )}
      {error && <div role="alert" className="text-sm text-destructive">{error}</div>}

      {!isLoading && !error && data && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                {data.columns.map(col => (
                  <TableHead key={col}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-auto p-0 font-medium hover:bg-transparent"
                      onClick={() => handleSort(col)}
                    >
                      {col}
                      {sortBy === col && sortOrder === 'asc' && (
                        <ChevronUp className="ml-1 h-4 w-4" aria-hidden="true" />
                      )}
                      {sortBy === col && sortOrder === 'desc' && (
                        <ChevronDown className="ml-1 h-4 w-4" aria-hidden="true" />
                      )}
                    </Button>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.rows.map((row, idx) => (
                <TableRow key={idx}>
                  {data.columns.map(col => (
                    <TableCell key={col}>{row[col]}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              Total rows: {data.total}
            </span>
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    onClick={() => setSkip(Math.max(0, skip - limit))}
                    aria-disabled={isPrevDisabled}
                    className={cn(isPrevDisabled && 'pointer-events-none opacity-50')}
                  />
                </PaginationItem>
                <PaginationItem>
                  <PaginationNext
                    onClick={() => setSkip(skip + limit)}
                    aria-disabled={isNextDisabled}
                    className={cn(isNextDisabled && 'pointer-events-none opacity-50')}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        </>
      )}
    </div>
  );
};
