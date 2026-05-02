/**
 * ResultTable — paginated/filterable view of one result table.
 *
 * Task 38C refactor: the single toolbar filter button is gone; every column
 * header now hosts an Excel-style ``ColumnFilterPopover`` whose layout
 * (enum / numeric / text) is auto-picked from backend ``column_meta``.
 * Multiple per-column filters AND together server-side and a chip row above
 * the table summarises them so the user can dismiss any one without
 * re-opening the popover.
 *
 * Dashboard-driven filters (route_type pie click, ligneId selection from the
 * map, etc.) flow in via the ``externalColumnFilters`` prop, which the parent
 * builds from the global FilterState.  Local popover changes are lifted back
 * out via ``onFilterChange`` for the columns mapped in
 * ``ENUM_FIELD_TO_FILTER_STATE_KEY``.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

import { downloadTableCsv, getTableData } from '@/api/client'
import type { ColumnFilter, ColumnMeta, TableDataResponse } from '@/types/api'
import { Button } from '@/components/atoms/button'
import {
  Pagination, PaginationContent, PaginationItem,
  PaginationNext, PaginationPrevious,
} from '@/components/ui/pagination'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  ColumnFilterPopover, ColumnFilterTrigger,
} from '@/components/molecules/ColumnFilterPopover'
import { ActiveFiltersChips } from '@/components/molecules/ActiveFiltersChips'
import {
  COLUMN_TYPE_OVERRIDES,
  ENUM_FIELD_TO_FILTER_STATE_KEY,
} from '@/lib/table-filter-config'
import type { FilterState } from '@/hooks/useDashboardSync'
import { cn } from '@/lib/utils'

interface ResultTableProps {
  projectId: string
  tableName: string
  /** Lifted from popover changes for columns mapped in
   *  ENUM_FIELD_TO_FILTER_STATE_KEY (route_type / id_ligne_num / id_ag_num). */
  onFilterChange?: (filters: Partial<FilterState>) => void
  /** Lifted on every local filter change with the COMPLETE filter map (mapped
   *  + non-mapped columns).  Used by the parent (TablePopup) to persist the
   *  filters in `useDashboardSync.state.tableFilters[tableId]` so they survive
   *  Dialog/ResultTable unmount and to trigger Phase 2 cross-pane resolution. */
  onAllColumnFiltersChange?: (filters: Record<string, ColumnFilter>) => void
  /** Filters pushed down by the parent dashboard (chart clicks, map
   *  selection, etc.).  Keyed by column name. */
  externalColumnFilters?: Record<string, ColumnFilter>
}

const DEFAULT_COLUMN_META: ColumnMeta = { type: 'text', total_distinct: 0 }

function filtersEqual(a: ColumnFilter, b: ColumnFilter): boolean {
  if (a.kind !== b.kind) return false
  if (a.kind === 'in' && b.kind === 'in') {
    if (a.values.length !== b.values.length) return false
    for (let i = 0; i < a.values.length; i++) if (a.values[i] !== b.values[i]) return false
    return true
  }
  if (a.kind === 'range' && b.kind === 'range') {
    return a.min === b.min && a.max === b.max
  }
  if (a.kind === 'contains' && b.kind === 'contains') {
    return a.term === b.term
  }
  return false
}

function recordsEqual(
  a: Record<string, ColumnFilter>,
  b: Record<string, ColumnFilter>,
): boolean {
  const ka = Object.keys(a)
  const kb = Object.keys(b)
  if (ka.length !== kb.length) return false
  for (const k of ka) {
    if (!(k in b)) return false
    if (!filtersEqual(a[k], b[k])) return false
  }
  return true
}

export const ResultTable: React.FC<ResultTableProps> = ({
  projectId,
  tableName,
  onFilterChange,
  onAllColumnFiltersChange,
  externalColumnFilters,
}) => {
  const [data, setData] = useState<TableDataResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)

  const [skip, setSkip] = useState(0)
  const [limit, setLimit] = useState(50)
  const [sortBy, setSortBy] = useState<string | undefined>(undefined)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')

  const [filters, setFilters] = useState<Record<string, ColumnFilter>>({})
  const [columnMeta, setColumnMeta] = useState<Record<string, ColumnMeta>>({})

  // Reset local UI state when the table changes (e.g. user opens another
  // table-popup) so leftover sort / filters / pagination don't leak across.
  useEffect(() => {
    setFilters({})
    setSkip(0)
    setSortBy(undefined)
    setSortOrder('asc')
    setColumnMeta({})
  }, [tableName])

  // Mirror the dashboard-driven filters into our local state.  Compared by
  // value so the parent can rebuild the object every render without churning
  // our state (matches the rationale of the original `externalKey` guard).
  const externalSerialised = useMemo(
    () => JSON.stringify(externalColumnFilters ?? {}),
    [externalColumnFilters],
  )
  useEffect(() => {
    const next = (externalColumnFilters ?? {}) as Record<string, ColumnFilter>
    setFilters((prev) => {
      // Preserve any columns the user has filtered locally that are NOT
      // mapped to a dashboard slot — they stay across chart-driven updates.
      const localOnly: Record<string, ColumnFilter> = {}
      for (const [col, f] of Object.entries(prev)) {
        if (!ENUM_FIELD_TO_FILTER_STATE_KEY[col]) {
          localOnly[col] = f
        }
      }
      const merged = { ...localOnly, ...next }
      return recordsEqual(prev, merged) ? prev : merged
    })
    setSkip(0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalSerialised])

  // Fetch table data on every relevant change.  column_meta=true on every
  // request — backend uses a bounded distinct-count so the cost is small,
  // and this guarantees fresh metadata when the project changes.
  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    getTableData(projectId, tableName, {
      skip,
      limit,
      sort_by: sortBy,
      sort_order: sortOrder,
      filters,
      column_meta: true,
    })
      .then((res) => {
        if (cancelled) return
        setData(res)
        if (res.column_meta) setColumnMeta(res.column_meta)
        setError(null)
      })
      .catch(() => {
        if (cancelled) return
        setError('Failed to load table data')
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, tableName, skip, limit, sortBy, sortOrder, filters])

  // Lift back filter changes inline from user-action callbacks.  We
  // deliberately do NOT do this in a useEffect on `filters` — that would also
  // fire on mount (with `filters === {}`) and on the mirror-from-external sync
  // path, wiping unrelated context slots and breaking dashboard linkage.
  const onFilterChangeRef = useRef(onFilterChange)
  onFilterChangeRef.current = onFilterChange
  const onAllColumnFiltersChangeRef = useRef(onAllColumnFiltersChange)
  onAllColumnFiltersChangeRef.current = onAllColumnFiltersChange

  const handleSortClick = useCallback((col: string) => {
    if (sortBy === col) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortOrder('asc')
    }
    setSkip(0)
  }, [sortBy, sortOrder])

  const handleFilterChange = useCallback(
    (col: string, next: ColumnFilter | null) => {
      setFilters((prev) => {
        const updated = { ...prev }
        if (next === null) delete updated[col]
        else updated[col] = next
        if (recordsEqual(prev, updated)) return prev
        // Lift the FULL record so the parent can persist it (Phase 1) and
        // trigger cross-pane resolve (Phase 2).
        onAllColumnFiltersChangeRef.current?.(updated)
        return updated
      })
      setSkip(0)

      const slot = ENUM_FIELD_TO_FILTER_STATE_KEY[col]
      const cb = onFilterChangeRef.current
      if (!slot || !cb) return
      const values = next?.kind === 'in' ? next.values : []
      if (slot === 'routeTypes') cb({ routeTypes: values })
      else if (slot === 'ligneIds') cb({ ligneIds: values.map(Number).filter(Number.isFinite) })
      else if (slot === 'agIds') cb({ agIds: values.map(Number).filter(Number.isFinite) })
    },
    [],
  )

  const handleSortChangeFromPopover = useCallback(
    (col: string, dir: 'asc' | 'desc' | null) => {
      if (dir === null) {
        setSortBy(undefined)
      } else {
        setSortBy(col)
        setSortOrder(dir)
      }
      setSkip(0)
    },
    [],
  )

  const removeFilter = useCallback((col: string) => {
    setFilters((prev) => {
      if (!(col in prev)) return prev
      const { [col]: _, ...rest } = prev
      const slot = ENUM_FIELD_TO_FILTER_STATE_KEY[col]
      const cb = onFilterChangeRef.current
      if (slot && cb) {
        if (slot === 'routeTypes') cb({ routeTypes: [] })
        else if (slot === 'ligneIds') cb({ ligneIds: [] })
        else if (slot === 'agIds') cb({ agIds: [] })
      }
      onAllColumnFiltersChangeRef.current?.(rest)
      return rest
    })
    setSkip(0)
  }, [])

  const clearAllFilters = useCallback(() => {
    setFilters((prev) => {
      const cb = onFilterChangeRef.current
      if (cb) {
        const partial: Partial<FilterState> = {}
        for (const [col, slot] of Object.entries(ENUM_FIELD_TO_FILTER_STATE_KEY)) {
          if (col in prev) {
            if (slot === 'routeTypes') partial.routeTypes = []
            else if (slot === 'ligneIds') partial.ligneIds = []
            else if (slot === 'agIds') partial.agIds = []
          }
        }
        if (Object.keys(partial).length) cb(partial)
      }
      onAllColumnFiltersChangeRef.current?.({})
      return {}
    })
    setSkip(0)
  }, [])

  const isPrevDisabled = skip === 0
  const isNextDisabled = data ? skip + limit >= data.total : true

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Button
          variant="outline"
          size="sm"
          disabled={isDownloading}
          onClick={() => {
            setIsDownloading(true)
            downloadTableCsv(projectId, tableName).finally(() => setIsDownloading(false))
          }}
        >
          {isDownloading ? 'Téléchargement…' : 'Download CSV'}
        </Button>

        <Select
          name="rows-per-page"
          value={String(limit)}
          onValueChange={(val) => {
            setLimit(Number(val))
            setSkip(0)
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

      <ActiveFiltersChips
        filters={filters}
        onRemove={removeFilter}
        onClearAll={clearAllFilters}
      />

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
                {data.columns.map((col) => {
                  const meta = columnMeta[col] ?? DEFAULT_COLUMN_META
                  const dataType = COLUMN_TYPE_OVERRIDES[col] ?? meta.type
                  const filter = filters[col] ?? null
                  const isFiltered = filter !== null
                  const isSorted = sortBy === col
                  const sortDir = isSorted ? sortOrder : null
                  return (
                    <TableHead key={col}>
                      <div className="flex items-center justify-between gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-auto p-0 font-medium hover:bg-transparent"
                          onClick={() => handleSortClick(col)}
                        >
                          {col}
                          {isSorted && sortOrder === 'asc' && (
                            <ChevronUp className="ml-1 h-4 w-4" aria-hidden="true" />
                          )}
                          {isSorted && sortOrder === 'desc' && (
                            <ChevronDown className="ml-1 h-4 w-4" aria-hidden="true" />
                          )}
                        </Button>
                        <ColumnFilterPopover
                          projectId={projectId}
                          tableName={tableName}
                          column={col}
                          dataType={dataType}
                          value={filter}
                          currentSort={sortDir}
                          onChange={(next) => handleFilterChange(col, next)}
                          onSortChange={(dir) => handleSortChangeFromPopover(col, dir)}
                        >
                          <ColumnFilterTrigger
                            active={isFiltered}
                            count={
                              filter?.kind === 'in' ? filter.values.length : undefined
                            }
                          />
                        </ColumnFilterPopover>
                      </div>
                    </TableHead>
                  )
                })}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.rows.map((row, idx) => (
                <TableRow key={idx}>
                  {data.columns.map((col) => (
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
  )
}
