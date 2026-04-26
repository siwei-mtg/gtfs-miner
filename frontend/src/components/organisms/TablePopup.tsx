/**
 * TablePopup — modal sheet that wraps <ResultTable> for the dashboard.
 *
 * Opens when the user clicks a row in the left sidebar; closes on overlay
 * click / Escape.  Only one table can be open at a time (enforced by the
 * parent page via a single `openTableId` state).  Local filter changes
 * inside ResultTable are lifted to the dashboard context so filters
 * persist across popups and light the sidebar funnel icon.
 */
import { useCallback, useMemo } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ResultTable } from '@/components/organisms/ResultTable'
import { useDashboardSync, type FilterState } from '@/hooks/useDashboardSync'
import { cn } from '@/lib/utils'

interface TablePopupProps {
  projectId: string
  tableId: string | null
  tableLabel?: string
  onClose: () => void
}

export function TablePopup({ projectId, tableId, tableLabel, onClose }: TablePopupProps) {
  const { state, dispatch } = useDashboardSync()

  // `state.ligneIds.map(String)` would otherwise rebuild the array on every
  // render, churning ResultTable's externalEnumValues prop and tripping
  // "Maximum update depth exceeded" inside Radix Dialog's usePresence.
  const externalEnumValues = useMemo<string[] | undefined>(() => {
    if (tableId === 'b1') return state.routeTypes
    if (tableId === 'b2') return state.ligneIds.map(String)
    return undefined
  }, [tableId, state.routeTypes, state.ligneIds])

  const handleFilterChange = useCallback(
    (f: Partial<FilterState>) => {
      if (f.routeTypes !== undefined) {
        dispatch({ type: 'SET_ROUTE_TYPES', payload: f.routeTypes })
      }
      if (f.ligneIds !== undefined) {
        dispatch({ type: 'SET_LIGNE_IDS', payload: f.ligneIds })
      }
    },
    [dispatch],
  )

  return (
    <Dialog
      open={tableId !== null}
      onOpenChange={(open) => { if (!open) onClose() }}
    >
      <DialogContent
        className={cn(
          'max-h-[90vh] w-[95vw] max-w-[75vw] gap-4 overflow-y-auto p-4 sm:p-6',
        )}
        data-testid={`table-popup-${tableId ?? 'closed'}`}
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
            externalEnumValues={externalEnumValues}
            onFilterChange={handleFilterChange}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
