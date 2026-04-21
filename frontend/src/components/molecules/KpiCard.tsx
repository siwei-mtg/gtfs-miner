/**
 * KpiCard — single-metric tile for the dashboard KPI row.
 *
 * A molecule: Icon + label + value, with a skeleton state while the 4
 * KPIs load.  Used inside DashboardRightPanel.
 */
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface KpiCardProps {
  label: string
  value: string | number | null
  icon?: LucideIcon
  /** If true, show a shimmer placeholder instead of the value. */
  loading?: boolean
  className?: string
}

export function KpiCard({ label, value, icon: Icon, loading, className }: KpiCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col justify-between rounded-lg border bg-card p-3',
        'min-h-[72px]',
        className,
      )}
      data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        {Icon && <Icon className="h-3.5 w-3.5" aria-hidden />}
        <span>{label}</span>
      </div>
      {loading ? (
        <div className="mt-1 h-6 w-16 animate-pulse rounded bg-muted" aria-hidden />
      ) : (
        <div className="mt-1 text-xl font-semibold tabular-nums">
          {value ?? '—'}
        </div>
      )}
    </div>
  )
}
