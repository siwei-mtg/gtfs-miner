/**
 * TableGroupHeader — section label for the left sidebar ("A · Agrégats",
 * "B · Lignes", …).  Purely presentational; rendered as a dimmed small-caps
 * header above each group of TableSidebarItems.
 */
import { cn } from '@/lib/utils'

interface TableGroupHeaderProps {
  letter: string
  label: string
  className?: string
}

export function TableGroupHeader({ letter, label, className }: TableGroupHeaderProps) {
  return (
    <div
      className={cn(
        'sticky top-0 z-10 bg-background/80 backdrop-blur px-2 py-1',
        'text-[11px] font-semibold uppercase tracking-wider text-muted-foreground',
        className,
      )}
    >
      <span className="text-foreground">{letter}</span>
      <span className="mx-1">·</span>
      <span>{label}</span>
    </div>
  )
}
