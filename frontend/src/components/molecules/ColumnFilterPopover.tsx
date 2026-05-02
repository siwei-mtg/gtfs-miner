/**
 * ColumnFilterPopover — Excel-style filter dropdown anchored to a table header.
 *
 * One molecule covers all three column types (enum / numeric / text).  The
 * caller passes the `dataType` it received from the backend's column_meta
 * payload, this component renders the matching layout:
 *
 *   - enum:    server-side distinct values + cmdk search + checklist
 *   - numeric: min / max number inputs (range)
 *   - text:    "Contient…" input that triggers a debounced server search
 *              feeding the same checklist (so the user can either type or
 *              pick from the suggestions, never both — see resolveFilter)
 *
 * Internal draft state:
 *   The user can tweak checks / range inputs freely; nothing is committed
 *   until they click "Appliquer".  "Effacer" emits null and closes.  Dismiss
 *   without applying (Esc / outside click) discards the draft.
 */
import * as React from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDownAZ, ArrowUpAZ } from 'lucide-react'

import { getColumnDistinct } from '@/api/client'
import type { ColumnDataType, ColumnFilter, DistinctValue } from '@/types/api'
import { Button } from '@/components/atoms/button'
import { Input } from '@/components/atoms/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { cn } from '@/lib/utils'
import { getColumnValueLabel } from '@/lib/table-filter-config'

const DISTINCT_LIMIT = 200
const SEARCH_DEBOUNCE_MS = 250

export type ColumnSort = 'asc' | 'desc' | null

interface ColumnFilterPopoverProps {
  projectId: string
  tableName: string
  column: string
  dataType: ColumnDataType
  /** Current filter on this column (parent-controlled).  null = no filter. */
  value: ColumnFilter | null
  /** Current sort applied to this column (or null when sorted by another col). */
  currentSort: ColumnSort
  onChange: (next: ColumnFilter | null) => void
  onSortChange: (dir: ColumnSort) => void
  /** The trigger element (typically a funnel icon button).  Wrapped by the
   *  Popover and used as the anchor point. */
  children: React.ReactNode
}

/** Convert checked values + contains term into the single ColumnFilter we emit.
 *
 *   - any value checked → 'in' (precedence over text input on hybrid layout)
 *   - else non-empty term → 'contains'
 *   - else null
 *
 * Numeric is handled separately in the inputs.
 */
function resolveTextFilter(checked: string[], term: string): ColumnFilter | null {
  if (checked.length > 0) return { kind: 'in', values: checked }
  if (term.trim()) return { kind: 'contains', term: term.trim() }
  return null
}

function rangeFromInputs(minStr: string, maxStr: string): ColumnFilter | null {
  const min = minStr.trim() === '' ? undefined : Number(minStr)
  const max = maxStr.trim() === '' ? undefined : Number(maxStr)
  if (min === undefined && max === undefined) return null
  if (min !== undefined && Number.isNaN(min)) return null
  if (max !== undefined && Number.isNaN(max)) return null
  return { kind: 'range', min, max }
}

export function ColumnFilterPopover({
  projectId,
  tableName,
  column,
  dataType,
  value,
  currentSort,
  onChange,
  onSortChange,
  children,
}: ColumnFilterPopoverProps) {
  const [open, setOpen] = useState(false)

  // Working copy — reset every time the popover (re)opens so cancelled drafts
  // don't bleed across openings.
  const initialChecked = value?.kind === 'in' ? value.values : []
  const initialContains = value?.kind === 'contains' ? value.term : ''
  const initialMin = value?.kind === 'range' && value.min !== undefined ? String(value.min) : ''
  const initialMax = value?.kind === 'range' && value.max !== undefined ? String(value.max) : ''

  const [checked, setChecked] = useState<string[]>(initialChecked)
  const [containsTerm, setContainsTerm] = useState<string>(initialContains)
  const [minStr, setMinStr] = useState<string>(initialMin)
  const [maxStr, setMaxStr] = useState<string>(initialMax)

  // Distinct-values fetch state (for enum + text layouts).
  const [distinct, setDistinct] = useState<DistinctValue[]>([])
  const [distinctLoading, setDistinctLoading] = useState(false)
  const [distinctError, setDistinctError] = useState<string | null>(null)
  const [distinctTruncated, setDistinctTruncated] = useState(false)

  // Reset draft state when (a) popover opens, (b) external value changes.
  useEffect(() => {
    if (!open) return
    setChecked(value?.kind === 'in' ? value.values : [])
    setContainsTerm(value?.kind === 'contains' ? value.term : '')
    setMinStr(value?.kind === 'range' && value.min !== undefined ? String(value.min) : '')
    setMaxStr(value?.kind === 'range' && value.max !== undefined ? String(value.max) : '')
  }, [open, value])

  // Load distinct values.  ``enum`` loads once on open; ``text`` re-loads on
  // each (debounced) containsTerm change so the suggestion list reflects the
  // current input.  ``numeric`` skips this entirely.
  const loadCounter = useRef(0)
  const fetchDistinct = useCallback(
    async (q: string) => {
      const ticket = ++loadCounter.current
      setDistinctLoading(true)
      setDistinctError(null)
      try {
        const res = await getColumnDistinct(projectId, tableName, column, {
          q: q || undefined,
          limit: DISTINCT_LIMIT,
        })
        if (loadCounter.current !== ticket) return  // stale response
        setDistinct(res.values)
        setDistinctTruncated(res.truncated)
      } catch {
        if (loadCounter.current !== ticket) return
        setDistinctError('Impossible de charger les valeurs')
      } finally {
        if (loadCounter.current === ticket) setDistinctLoading(false)
      }
    },
    [projectId, tableName, column],
  )

  useEffect(() => {
    if (!open) return
    if (dataType === 'numeric') return
    if (dataType === 'enum') {
      fetchDistinct('')
      return
    }
    // text: debounce search
    const handle = window.setTimeout(() => {
      fetchDistinct(containsTerm)
    }, SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(handle)
  }, [open, dataType, containsTerm, fetchDistinct])

  const allChecked = useMemo(() => {
    if (distinct.length === 0) return false
    return distinct.every((v) => checked.includes(String(v.value)))
  }, [distinct, checked])

  const toggleAll = () => {
    if (allChecked) setChecked([])
    else setChecked(distinct.map((v) => String(v.value)))
  }

  const toggleOne = (raw: string) => {
    setChecked((prev) =>
      prev.includes(raw) ? prev.filter((v) => v !== raw) : [...prev, raw],
    )
  }

  const apply = () => {
    if (dataType === 'numeric') {
      onChange(rangeFromInputs(minStr, maxStr))
    } else if (dataType === 'enum') {
      onChange(checked.length > 0 ? { kind: 'in', values: checked } : null)
    } else {
      onChange(resolveTextFilter(checked, containsTerm))
    }
    setOpen(false)
  }

  const clear = () => {
    onChange(null)
    setOpen(false)
  }

  const renderSortHeader = (
    <div className="flex gap-1 pb-2 border-b border-hair">
      <Button
        variant={currentSort === 'asc' ? 'secondary' : 'ghost'}
        size="sm"
        className="h-7 px-2 text-xs flex-1 justify-start"
        onClick={() => onSortChange(currentSort === 'asc' ? null : 'asc')}
      >
        <ArrowUpAZ className="mr-1 h-3.5 w-3.5" /> A → Z
      </Button>
      <Button
        variant={currentSort === 'desc' ? 'secondary' : 'ghost'}
        size="sm"
        className="h-7 px-2 text-xs flex-1 justify-start"
        onClick={() => onSortChange(currentSort === 'desc' ? null : 'desc')}
      >
        <ArrowDownAZ className="mr-1 h-3.5 w-3.5" /> Z → A
      </Button>
    </div>
  )

  const renderFooter = (
    <div className="flex justify-between items-center gap-2 pt-2 border-t border-hair">
      <Button variant="ghost" size="sm" onClick={clear} className="h-7 px-2 text-xs">
        Effacer
      </Button>
      <Button size="sm" onClick={apply} className="h-7 px-3 text-xs">
        Appliquer
      </Button>
    </div>
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent
        className="w-[260px] p-2"
        onClick={(e) => e.stopPropagation()}
        onPointerDown={(e) => e.stopPropagation()}
      >
        {renderSortHeader}

        <div className="py-2">
          {dataType === 'numeric' && (
            <div className="space-y-2">
              <label className="block text-xs">
                <span className="text-muted-foreground mb-1 block">≥ min</span>
                <Input
                  type="number"
                  value={minStr}
                  onChange={(e) => setMinStr(e.target.value)}
                  className="h-8 text-sm"
                  placeholder="min"
                />
              </label>
              <label className="block text-xs">
                <span className="text-muted-foreground mb-1 block">≤ max</span>
                <Input
                  type="number"
                  value={maxStr}
                  onChange={(e) => setMaxStr(e.target.value)}
                  className="h-8 text-sm"
                  placeholder="max"
                />
              </label>
            </div>
          )}

          {dataType === 'enum' && (
            <Command>
              <CommandInput placeholder="Rechercher…" className="h-8" />
              <div className="flex justify-end px-1 pt-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={toggleAll}
                  className="h-6 px-2 text-[11px]"
                  disabled={distinct.length === 0}
                >
                  {allChecked ? 'Tout décocher' : 'Tout cocher'}
                </Button>
              </div>
              <CommandList>
                {distinctError && (
                  <div role="alert" className="px-2 py-1 text-xs text-destructive">
                    {distinctError}
                  </div>
                )}
                {distinctLoading && distinct.length === 0 && (
                  <div className="px-2 py-1 text-xs text-muted-foreground">Chargement…</div>
                )}
                <CommandEmpty>Aucune valeur</CommandEmpty>
                {distinct.map((v) => {
                  const raw = String(v.value)
                  const isChecked = checked.includes(raw)
                  return (
                    <CommandItem
                      key={raw}
                      value={raw + ' ' + getColumnValueLabel(column, v.value)}
                      onSelect={() => toggleOne(raw)}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        readOnly
                        className="h-3.5 w-3.5 accent-primary"
                        aria-label={raw}
                      />
                      <span className="flex-1 truncate">{getColumnValueLabel(column, v.value)}</span>
                      <span className="text-[11px] text-muted-foreground tabular-nums">{v.count}</span>
                    </CommandItem>
                  )
                })}
                {distinctTruncated && (
                  <div className="px-2 py-1 text-[11px] text-muted-foreground">
                    Liste tronquée — affinez la recherche.
                  </div>
                )}
              </CommandList>
            </Command>
          )}

          {dataType === 'text' && (
            <div className="space-y-2">
              <Input
                type="text"
                value={containsTerm}
                onChange={(e) => setContainsTerm(e.target.value)}
                className="h-8 text-sm"
                placeholder="Contient…"
              />
              <Command shouldFilter={false}>
                <CommandList className="max-h-[180px]">
                  {distinctError && (
                    <div role="alert" className="px-2 py-1 text-xs text-destructive">
                      {distinctError}
                    </div>
                  )}
                  {distinctLoading && (
                    <div className="px-2 py-1 text-xs text-muted-foreground">Chargement…</div>
                  )}
                  {!distinctLoading && distinct.length === 0 && containsTerm && (
                    <CommandEmpty>Aucune valeur</CommandEmpty>
                  )}
                  {distinct.map((v) => {
                    const raw = String(v.value)
                    const isChecked = checked.includes(raw)
                    return (
                      <CommandItem
                        key={raw}
                        value={raw}
                        onSelect={() => toggleOne(raw)}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          readOnly
                          className="h-3.5 w-3.5 accent-primary"
                          aria-label={raw}
                        />
                        <span className="flex-1 truncate">{raw}</span>
                        <span className="text-[11px] text-muted-foreground tabular-nums">{v.count}</span>
                      </CommandItem>
                    )
                  })}
                  {distinctTruncated && (
                    <div className="px-2 py-1 text-[11px] text-muted-foreground">
                      Liste tronquée — affinez la recherche.
                    </div>
                  )}
                </CommandList>
              </Command>
            </div>
          )}
        </div>

        {renderFooter}
      </PopoverContent>
    </Popover>
  )
}

ColumnFilterPopover.displayName = 'ColumnFilterPopover'

interface ColumnFilterTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active: boolean
  count?: number
}

/**
 * Funnel icon that lives next to a column header.  Becomes a primary-coloured
 * pill when a filter is active so the user can see at a glance which columns
 * are filtered without opening every popover.
 *
 * Must forward refs so Radix' ``<PopoverTrigger asChild>`` can attach the
 * trigger element to floating-ui — otherwise the popover renders without a
 * known anchor and ends up positioned at (0,0), invisible to the user.
 */
export const ColumnFilterTrigger = React.forwardRef<
  HTMLButtonElement,
  ColumnFilterTriggerProps
>(function ColumnFilterTrigger({ active, count, className, ...props }, ref) {
  return (
    <button
      {...props}
      ref={ref}
      type="button"
      className={cn(
        'inline-flex h-6 w-6 items-center justify-center rounded-md transition-colors',
        active
          ? 'bg-primary/15 text-primary hover:bg-primary/25'
          : 'text-muted-foreground/70 opacity-60 hover:opacity-100 hover:bg-accent',
        className,
      )}
      aria-label={active ? `Filtre actif (${count ?? ''})` : 'Filtrer la colonne'}
    >
      {/* Lucide Filter icon, drawn inline so the wrapper stays atom-pure. */}
      <svg
        viewBox="0 0 24 24"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
      </svg>
    </button>
  )
})
