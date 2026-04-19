import React, { useEffect, useMemo, useRef, useState } from 'react';
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
import { MultiSelectFilter } from '@/components/molecules/MultiSelectFilter';
import { RangeFilter, type RangeValue } from '@/components/molecules/RangeFilter';
import {
  ENUM_FIELD_TO_FILTER_STATE_KEY,
  PRIMARY_ENUM_FIELD,
  PRIMARY_NUMERIC_FIELD,
  getEnumOptions,
} from '@/lib/table-filter-config';
import type { FilterState } from '@/hooks/useDashboardSync';

interface ResultTableProps {
  projectId: string;
  tableName: string;
  /** Called whenever local filter state changes; emits the subset of FilterState
   *  this table contributes to (e.g. { routeTypes: ['3'] } when filtering B_1). */
  onFilterChange?: (filters: Partial<FilterState>) => void;
  /** When provided, the primary-enum filter is controlled from outside (e.g.
   *  the Dashboard context); local selection mirrors the prop on change. */
  externalEnumValues?: string[];
}

export const ResultTable: React.FC<ResultTableProps> = ({
  projectId,
  tableName,
  onFilterChange,
  externalEnumValues,
}) => {
  const [data, setData] = useState<TableDataResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(50);
  const [sortBy, setSortBy] = useState<string | undefined>(undefined);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  const enumField = PRIMARY_ENUM_FIELD[tableName];
  const numericField = PRIMARY_NUMERIC_FIELD[tableName];
  const [enumValues, setEnumValues] = useState<string[]>([]);
  const [rangeValue, setRangeValue] = useState<RangeValue>({});

  // Reset filters when switching between tables so stale values don't leak.
  useEffect(() => {
    setEnumValues([]);
    setRangeValue({});
    setSkip(0);
  }, [tableName]);

  // When the Dashboard pushes down a new selection (e.g. user clicked a Pie
  // sector) mirror it locally so the filter chip and backend request update.
  const externalKey = externalEnumValues ? externalEnumValues.join(',') : null;
  useEffect(() => {
    if (externalEnumValues === undefined) return;
    setEnumValues(externalEnumValues);
    setSkip(0);
  }, [externalKey, externalEnumValues]);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);

    getTableData(projectId, tableName, {
      skip,
      limit,
      sort_by: sortBy,
      sort_order: sortOrder,
      filter_field: enumField && enumValues.length > 0 ? enumField : undefined,
      filter_values: enumField && enumValues.length > 0 ? enumValues : undefined,
      range_field:
        numericField && (rangeValue.min !== undefined || rangeValue.max !== undefined)
          ? numericField
          : undefined,
      range_min: rangeValue.min,
      range_max: rangeValue.max,
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
  }, [projectId, tableName, skip, limit, sortBy, sortOrder, enumField, enumValues, numericField, rangeValue]);

  // Lift filter state up to the parent dashboard, but only for enum columns
  // that map onto the global FilterState (route_type, id_ligne_num, id_ag_num).
  const onFilterChangeRef = useRef(onFilterChange);
  onFilterChangeRef.current = onFilterChange;
  useEffect(() => {
    if (!onFilterChangeRef.current) return;
    if (!enumField) return;
    const key = ENUM_FIELD_TO_FILTER_STATE_KEY[enumField];
    if (!key) return;
    const coerced =
      key === 'routeTypes'
        ? enumValues
        : (enumValues.map((v) => Number(v)).filter((n) => Number.isFinite(n)) as Array<string | number>);
    onFilterChangeRef.current({ [key]: coerced } as unknown as Partial<FilterState>);
  }, [enumField, enumValues]);

  const enumOptions = useMemo(
    () => (enumField ? getEnumOptions(enumField, data?.rows.map((r) => r[enumField]) ?? []) : []),
    [enumField, data],
  );

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
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
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

          {enumField && (
            <MultiSelectFilter
              field={enumField}
              options={enumOptions}
              selected={enumValues}
              onChange={(next) => {
                setEnumValues(next);
                setSkip(0);
              }}
            />
          )}
          {numericField && (
            <RangeFilter
              field={numericField}
              value={rangeValue}
              onChange={(next) => {
                setRangeValue(next);
                setSkip(0);
              }}
            />
          )}
        </div>

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
