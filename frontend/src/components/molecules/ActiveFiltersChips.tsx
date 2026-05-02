/**
 * ActiveFiltersChips — compact summary of the column filters currently
 * applied to a ResultTable.  Renders one chip per active filter with the
 * column label and a brief description of the filter (values listed for
 * `in`, bounds for `range`, term for `contains`).  Click ✕ → remove.
 *
 * "Effacer tout" appears on the right when there is more than one chip.
 */
import { X } from 'lucide-react'

import type { ColumnFilter } from '@/types/api'
import { Button } from '@/components/atoms/button'
import { getColumnValueLabel } from '@/lib/table-filter-config'

interface ActiveFiltersChipsProps {
  filters: Record<string, ColumnFilter>
  onRemove: (column: string) => void
  onClearAll?: () => void
}

function describeFilter(column: string, f: ColumnFilter): string {
  if (f.kind === 'in') {
    if (f.values.length <= 3) {
      return f.values.map((v) => getColumnValueLabel(column, v)).join(', ')
    }
    return `${f.values.length} valeurs`
  }
  if (f.kind === 'range') {
    if (f.min !== undefined && f.max !== undefined) return `${f.min} – ${f.max}`
    if (f.min !== undefined) return `≥ ${f.min}`
    if (f.max !== undefined) return `≤ ${f.max}`
    return ''
  }
  return `« ${f.term} »`
}

export function ActiveFiltersChips({
  filters,
  onRemove,
  onClearAll,
}: ActiveFiltersChipsProps) {
  const entries = Object.entries(filters)
  if (entries.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {entries.map(([column, filter]) => (
        <span
          key={column}
          className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary"
        >
          <span className="font-medium">{column}</span>
          <span className="text-primary/80">: {describeFilter(column, filter)}</span>
          <button
            type="button"
            onClick={() => onRemove(column)}
            className="rounded-full p-0.5 hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            aria-label={`Retirer le filtre ${column}`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      {entries.length > 1 && onClearAll && (
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs"
          onClick={onClearAll}
        >
          Effacer tout
        </Button>
      )}
    </div>
  )
}
