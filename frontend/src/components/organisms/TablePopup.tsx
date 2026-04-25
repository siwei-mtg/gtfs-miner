/**
 * TablePopup — modal sheet that wraps <ResultTable> for the dashboard.
 *
 * Opens when the user clicks a row in the left sidebar; closes on overlay
 * click / Escape.  Only one table can be open at a time (enforced by the
 * parent page via a single `openTableId` state).  Local filter changes
 * inside ResultTable are lifted to the dashboard context so filters
 * persist across popups and light the sidebar funnel icon.
 */
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ResultTable } from '@/components/organisms/ResultTable'
import { useDashboardSync } from '@/hooks/useDashboardSync'
import { cn } from '@/lib/utils'

interface TablePopupProps {
  projectId: string
  tableId: string | null
  tableLabel?: string
  onClose: () => void
}

export function TablePopup({ projectId, tableId, tableLabel, onClose }: TablePopupProps) {
  const { state, dispatch } = useDashboardSync()

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
            externalEnumValues={tableId === 'b1' ? state.routeTypes : undefined}
            onFilterChange={(f) => {
              if (f.routeTypes !== undefined) {
                dispatch({ type: 'SET_ROUTE_TYPES', payload: f.routeTypes })
              }
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
