/**
 * TablePopup — modal sheet that wraps <ResultTable> for the dashboard.
 *
 * Opens when the user clicks a row in the left sidebar; closes on overlay
 * click / Escape.  Only one table can be open at a time (enforced by the
 * parent page via a single `openTableId` state).
 *
 * Filter wiring:
 *   - `externalColumnFilters` mirrors `state.tableFilters[tableId]` only —
 *     the user's local per-column filters that survive Dialog unmount.
 *   - `contextFilters` is the NEW path: when another table's filter or a
 *     chart click set canonical slots (state.ligneIds / .routeTypes /
 *     .agIds), we AND-merge the matching columns into THIS table's fetch
 *     so the data the user sees actually reflects the global context.
 *     Restricted by `TABLE_COLUMNS` so we don't try to filter by a column
 *     the table doesn't have (E_1/E_4 lack id_ligne_num — they stay
 *     unfiltered, and `isTableFiltered` matches that reality).
 *     contextFilters are NOT shown as chips and NOT lifted back, so they
 *     can't loop into `tableFilters[tableId]` and persist as a fake user
 *     filter.
 *   - The "source" table — whose own tableFilters drove the current
 *     ligneIds/routeTypes via /resolve — is exempted from contextFilters
 *     (state.resolveSource === tableId).  Re-applying the canonical IDs
 *     there is a no-op (the local filter is strictly more restrictive)
 *     but would surface a "filtered by context" banner on the very table
 *     the user is filtering, which is confusing.
 *
 * Resolve dispatch:
 *   - `handleAllFiltersChange` dispatches `SET_TABLE_FILTERS` (Phase 1 —
 *     survives unmount) AND debounce-calls /tables/{name}/resolve.  The
 *     resolve result fires ONE combined `APPLY_RESOLVED` action that
 *     atomically writes ligneIds + routeTypes + resolveSource.
 *   - When the user clears all filters on a table, we deliberately SKIP
 *     the resolve call — wiping state.routeTypes / state.ligneIds from
 *     this path would silently undo unrelated chart-driven selections.
 *     For a global reset use "Effacer tout" in DashboardHeader.
 */
import { useCallback, useEffect, useMemo, useRef } from 'react'

import { resolveTableFilters } from '@/api/client'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ResultTable } from '@/components/organisms/ResultTable'
import { useDashboardSync, type FilterState } from '@/hooks/useDashboardSync'
import { TABLE_COLUMNS } from '@/lib/table-filter-config'
import type { ColumnFilter } from '@/types/api'
import { cn } from '@/lib/utils'

const RESOLVE_DEBOUNCE_MS = 250

interface TablePopupProps {
  projectId: string
  tableId: string | null
  tableLabel?: string
  onClose: () => void
}

function describeContext(ctx: Record<string, ColumnFilter>): string {
  const parts: string[] = []
  const ligne = ctx.id_ligne_num
  if (ligne?.kind === 'in') {
    const n = ligne.values.length
    parts.push(`${n} ligne${n > 1 ? 's' : ''}`)
  }
  const rt = ctx.route_type
  if (rt?.kind === 'in') {
    const n = rt.values.length
    parts.push(`${n} type${n > 1 ? 's' : ''} d'arrêt`)
  }
  const ag = ctx.id_ag_num
  if (ag?.kind === 'in') {
    const n = ag.values.length
    parts.push(`${n} arrêt${n > 1 ? 's' : ''}`)
  }
  return parts.join(', ')
}

export function TablePopup({ projectId, tableId, tableLabel, onClose }: TablePopupProps) {
  const { state, dispatch } = useDashboardSync()

  const externalColumnFilters = useMemo<Record<string, ColumnFilter>>(() => {
    if (!tableId) return {}
    return state.tableFilters[tableId] ?? {}
  }, [tableId, state.tableFilters])

  const contextFilters = useMemo<Record<string, ColumnFilter>>(() => {
    if (!tableId) return {}
    // The table whose local filter triggered the current resolution skips
    // its own context — its tableFilters is strictly more restrictive.
    if (state.resolveSource === tableId) return {}
    const cols = TABLE_COLUMNS[tableId] ?? new Set<string>()
    const local = state.tableFilters[tableId] ?? {}
    const out: Record<string, ColumnFilter> = {}
    if (cols.has('id_ligne_num') && state.ligneIds.length > 0 && !local.id_ligne_num) {
      out.id_ligne_num = { kind: 'in', values: state.ligneIds.map(String) }
    }
    if (cols.has('route_type') && state.routeTypes.length > 0 && !local.route_type) {
      out.route_type = { kind: 'in', values: state.routeTypes }
    }
    if (cols.has('id_ag_num') && state.agIds.length > 0 && !local.id_ag_num) {
      out.id_ag_num = { kind: 'in', values: state.agIds.map(String) }
    }
    return out
  }, [
    tableId,
    state.resolveSource,
    state.ligneIds,
    state.routeTypes,
    state.agIds,
    state.tableFilters,
  ])

  const contextDescription = useMemo(() => describeContext(contextFilters), [contextFilters])

  const handleFilterChange = useCallback(
    (f: Partial<FilterState>) => {
      if (f.routeTypes !== undefined) {
        dispatch({ type: 'SET_ROUTE_TYPES', payload: f.routeTypes })
      }
      if (f.ligneIds !== undefined) {
        dispatch({ type: 'SET_LIGNE_IDS', payload: f.ligneIds })
      }
      if (f.agIds !== undefined) {
        dispatch({ type: 'SET_AG_IDS', payload: f.agIds })
      }
    },
    [dispatch],
  )

  const resolveTimerRef = useRef<number | null>(null)
  const lastResolveKeyRef = useRef<string>('')

  const scheduleResolve = useCallback(
    (filters: Record<string, ColumnFilter>) => {
      if (!tableId) return
      if (resolveTimerRef.current !== null) {
        window.clearTimeout(resolveTimerRef.current)
        resolveTimerRef.current = null
      }
      // Empty filter set → skip resolve so we don't clobber chart-set slots.
      if (Object.keys(filters).length === 0) {
        lastResolveKeyRef.current = ''
        return
      }
      const tid = tableId
      resolveTimerRef.current = window.setTimeout(() => {
        resolveTimerRef.current = null
        const key = JSON.stringify(filters)
        if (key === lastResolveKeyRef.current) return
        lastResolveKeyRef.current = key
        resolveTableFilters(projectId, tid, filters)
          .then((res) => {
            dispatch({
              type: 'APPLY_RESOLVED',
              payload: {
                ligneIds: res.ligne_ids,
                routeTypes: res.route_types,
                agIds: res.ag_ids,
                source: tid,
              },
            })
          })
          .catch((err) => {
            console.error('resolveTableFilters failed:', err)
          })
      }, RESOLVE_DEBOUNCE_MS) as unknown as number
    },
    [projectId, tableId, dispatch],
  )

  const handleAllFiltersChange = useCallback(
    (filters: Record<string, ColumnFilter>) => {
      if (!tableId) return
      dispatch({ type: 'SET_TABLE_FILTERS', tableId, payload: filters })
      scheduleResolve(filters)
    },
    [dispatch, tableId, scheduleResolve],
  )

  // Cancel any pending resolve when the popup closes / unmounts so a stale
  // request doesn't dispatch into a fresh dashboard state.
  useEffect(() => () => {
    if (resolveTimerRef.current !== null) {
      window.clearTimeout(resolveTimerRef.current)
      resolveTimerRef.current = null
    }
  }, [])

  return (
    <Dialog
      open={tableId !== null}
      onOpenChange={(open) => { if (!open) onClose() }}
      // Non-modal so the column-filter popovers (portaled to <body>) can
      // receive pointer events.  Radix' modal=true puts pointer-events:none
      // on everything outside the DialogContent — that swallows clicks on
      // the popover, leaving it invisible/non-interactive.
      modal={false}
    >
      <DialogContent
        className={cn(
          'max-h-[90vh] w-[95vw] max-w-[75vw] gap-4 overflow-y-auto p-4 sm:p-6',
        )}
        data-testid={`table-popup-${tableId ?? 'closed'}`}
        // Prevent the Dialog from closing when the user interacts with a
        // column-filter popover (portaled outside DialogContent).  Without
        // this guard, every click inside the popover bubbles to Radix' outside
        // detector and dismisses the whole table.
        onInteractOutside={(e) => {
          const target = e.target as Element | null
          if (target?.closest('[data-radix-popper-content-wrapper]')) {
            e.preventDefault()
          }
        }}
      >
        <DialogHeader>
          <DialogTitle className="text-base font-semibold">
            {tableLabel ?? tableId?.toUpperCase() ?? 'Table'}
          </DialogTitle>
        </DialogHeader>
        {tableId && contextDescription && (
          <div
            className="rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground"
            data-testid="context-filter-banner"
          >
            <span className="font-medium text-foreground">Filtré par contexte global · </span>
            {contextDescription}
            <span className="ml-1">
              — utilisez « Effacer tout » dans l'en-tête pour réinitialiser.
            </span>
          </div>
        )}
        {tableId && (
          <ResultTable
            projectId={projectId}
            tableName={tableId}
            externalColumnFilters={externalColumnFilters}
            contextFilters={contextFilters}
            onFilterChange={handleFilterChange}
            onAllColumnFiltersChange={handleAllFiltersChange}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
