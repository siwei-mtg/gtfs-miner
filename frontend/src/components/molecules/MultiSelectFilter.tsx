/**
 * MultiSelectFilter — popover-style checkbox list for enum filtering (Task 38B).
 *
 * Uses native `<details>` + checkboxes to stay zero-dependency; Radix
 * Popover would require pulling in another primitive for marginal gain.
 */
import type { FilterOption } from '@/lib/table-filter-config'
import { Button } from '@/components/atoms/button'
import { cn } from '@/lib/utils'

interface Props {
  field: string
  options: FilterOption[]
  selected: string[]
  onChange: (values: string[]) => void
  className?: string
}

export function MultiSelectFilter({ field, options, selected, onChange, className }: Props) {
  const label = selected.length === 0 ? `${field} · Tout` : `${field} · ${selected.length}`

  const toggle = (value: string, checked: boolean) => {
    if (checked) onChange([...selected, value])
    else onChange(selected.filter((v) => v !== value))
  }

  return (
    <details className={cn('relative inline-block', className)}>
      <summary className="list-none marker:hidden cursor-pointer">
        <Button
          asChild
          size="sm"
          variant={selected.length > 0 ? 'default' : 'outline'}
        >
          <span aria-label={`${field}-filter-trigger`}>{label}</span>
        </Button>
      </summary>
      <div
        role="group"
        aria-label={`${field}-filter-options`}
        className="absolute left-0 z-10 mt-1 w-56 rounded-md border bg-popover p-2 shadow-lg"
      >
        {options.length === 0 && (
          <div className="px-1 py-1 text-xs text-muted-foreground">Aucune valeur</div>
        )}
        {options.map((opt) => {
          const isChecked = selected.includes(opt.value)
          return (
            <label
              key={opt.value}
              className="flex items-center gap-2 rounded px-1 py-1 text-sm hover:bg-accent"
            >
              <input
                type="checkbox"
                checked={isChecked}
                onChange={(e) => toggle(opt.value, e.target.checked)}
                aria-label={`${field}-option-${opt.value}`}
              />
              <span>{opt.label}</span>
            </label>
          )
        })}
        {selected.length > 0 && (
          <button
            type="button"
            className="mt-1 w-full rounded px-1 py-1 text-left text-xs text-muted-foreground hover:bg-accent"
            onClick={() => onChange([])}
          >
            Réinitialiser
          </button>
        )}
      </div>
    </details>
  )
}
