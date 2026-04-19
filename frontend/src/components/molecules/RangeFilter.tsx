/**
 * RangeFilter — numeric min/max input pair for column filtering (Task 38B).
 */
import { Input } from '@/components/atoms/input'
import { cn } from '@/lib/utils'

export interface RangeValue {
  min?: number
  max?: number
}

interface Props {
  field: string
  value: RangeValue
  onChange: (value: RangeValue) => void
  className?: string
}

function toNumberOrUndefined(raw: string): number | undefined {
  if (raw === '') return undefined
  const n = Number(raw)
  return Number.isFinite(n) ? n : undefined
}

export function RangeFilter({ field, value, onChange, className }: Props) {
  return (
    <div className={cn('flex items-center gap-2', className)} aria-label={`${field}-range-filter`}>
      <span className="text-sm text-muted-foreground">{field}</span>
      <Input
        type="number"
        placeholder="min"
        className="h-8 w-20 text-sm"
        aria-label={`${field} min`}
        value={value.min ?? ''}
        onChange={(e) => onChange({ ...value, min: toNumberOrUndefined(e.target.value) })}
      />
      <span className="text-muted-foreground">–</span>
      <Input
        type="number"
        placeholder="max"
        className="h-8 w-20 text-sm"
        aria-label={`${field} max`}
        value={value.max ?? ''}
        onChange={(e) => onChange({ ...value, max: toNumberOrUndefined(e.target.value) })}
      />
    </div>
  )
}
