/**
 * TableSidebarItem — one clickable row in the left-hand "15 tables" sidebar.
 *
 * Two-line layout: bold code (e.g. "A_1") above a muted full name, and an
 * optional funnel icon on the right that lights up whenever a global filter
 * is currently narrowing this table.
 */
import { Filter } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TableSidebarItemProps {
  /** Short id used for DOM testids (e.g. "a1"). */
  id: string
  code: string
  name: string
  filtered?: boolean
  active?: boolean
  onClick?: () => void
  className?: string
}

export function TableSidebarItem({
  id,
  code,
  name,
  filtered,
  active,
  onClick,
  className,
}: TableSidebarItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active ?? false}
      className={cn(
        'group flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left',
        'transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        active && 'bg-accent',
        className,
      )}
      data-testid={`sidebar-table-${id}`}
    >
      <span className="min-w-0">
        <span className="block text-[13px] font-semibold leading-tight">{code}</span>
        <span className="block truncate text-[11px] leading-tight text-muted-foreground">
          {name}
        </span>
      </span>
      {filtered && (
        <Filter
          className="h-3.5 w-3.5 shrink-0 text-primary"
          aria-label="Filtres actifs"
        />
      )}
    </button>
  )
}
