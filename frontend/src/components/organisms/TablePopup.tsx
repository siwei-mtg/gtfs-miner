/**
 * TablePopup — modal sheet that wraps <ResultTable> for the dashboard.
 *
 * Opens when the user clicks a row in the left sidebar; closes on overlay
 * click / Escape.  Only one table can be open at a time (enforced by the
 * parent page via a single `openTableId` state).
 *
 * Filter wiring (post-Bug-A fix):
 *   - `externalColumnFilters` reads from `state.tableFilters[tableId]` only.
 *     The previous mirror "mapped slot → primary column" was removed because
 *     it caused a visual loop after Phase-2 resolution (resolved ligne_ids
 *     would re-appear as a chip in the same table).
 *   - `handleFilterChange` (Partial<FilterState>) keeps the existing direct
 *     dispatch path for mapped columns (route_type / id_ligne_num / id_ag_num).
 *   - `handleAllFiltersChange` is the new persistence + cross-pane path:
 *     dispatches `SET_TABLE_FILTERS` (Phase 1 — survives unmount) AND
 *     debounce-calls /tables/{name}/resolve to translate any non-trivial
 *     filter set into canonical ligne_ids / route_types (Phase 2).
 *   - When the user clears all filters on a table, we deliberately SKIP the
 *     resolve call — wiping `state.routeTypes` / `state.ligneIds` from this
 *     path would silently undo unrelated chart-driven selections.  For a
 *     global reset use the "Effacer tout" button in DashboardHeader.
 */
import { useCallback, useEffect, useMemo, useRef } from 'react'

import { resolveTableFilters } from '@/api/client'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ResultTable } from '@/components/organisms/ResultTable'
import { useDashboardSync, type FilterState } from '@/hooks/useDashboardSync'
import type { ColumnFilter } from '@/types/api'
import { cn } from '@/lib/utils'

const RESOLVE_DEBOUNCE_MS = 250

interface TablePopupProps {
  projectId: string
  tableId: string | null
  tableLabel?: string
  onClose: () => void
}

export function TablePopup({ projectId, tableId, tableLabel, onClose }: TablePopupProps) {
  const { state, dispatch } = useDashboardSync()

  const externalColumnFilters = useMemo<Record<string, ColumnFilter>>(() => {
    if (!tableId) return {}
    return state.tableFilters[tableId] ?? {}
  }, [tableId, state.tableFilters])

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
            dispatch({ type: 'SET_LIGNE_IDS', payload: res.ligne_ids })
            dispatch({ type: 'SET_ROUTE_TYPES', payload: res.route_types })
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
        {tableId && (
          <ResultTable
            projectId={projectId}
            tableName={tableId}
            externalColumnFilters={externalColumnFilters}
            onFilterChange={handleFilterChange}
            onAllColumnFiltersChange={handleAllFiltersChange}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
