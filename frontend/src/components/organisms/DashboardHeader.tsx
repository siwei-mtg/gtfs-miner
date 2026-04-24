/**
 * DashboardHeader — top bar of the unified project page.
 *
 *   [← Projets]  [project name]  [id]  ·  ✓ Terminé · 12 s · 📋 Journal
 *                                    ──────────────────────────────────
 *                                    [🔄 Réinitialiser (N)]  [📥 Export ▾]
 *
 * The status strip + Journal dialog stay in the header so the processing
 * trace remains one click away even after completion, without occupying
 * prime page real estate (which goes to the analytical panes).
 */
import { Link } from 'react-router-dom'
import { Check, ChevronLeft, ClipboardList, Download, X } from 'lucide-react'

import { Button } from '@/components/atoms/button'
import { CodeTag } from '@/components/atoms/CodeTag'
import { Pastille } from '@/components/atoms/Pastille'
import { Hairline } from '@/components/atoms/Hairline'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ProgressPanel } from '@/components/organisms/ProgressPanel'
import { activeFilterCount, useDashboardSync } from '@/hooks/useDashboardSync'
import { cn } from '@/lib/utils'
import type { WebSocketMessage } from '@/types/api'

interface Props {
  projectId: string
  /** Display name for the project; falls back to the ID when the project
   *  schema has no human label yet. */
  projectName?: string
  /** Full progress feed for the Journal dialog and the elapsed-time chip. */
  progressMessages: WebSocketMessage[]
  /** Invoked when the user picks GeoPackage from the export dropdown. */
  onExportGeoPackage: () => void
  /** Invoked when the user picks CSV zip from the export dropdown. */
  onExportCsvZip: () => void
  className?: string
}

export function DashboardHeader({
  projectId,
  projectName,
  progressMessages,
  onExportGeoPackage,
  onExportCsvZip,
  className,
}: Props) {
  const { state, dispatch } = useDashboardSync()
  const count = activeFilterCount(state)
  const elapsed = progressMessages.at(-1)?.time_elapsed

  return (
    <div className={cn('flex items-center gap-3 px-4 py-2', className)}>
      <Button asChild variant="ghost" size="sm" className="h-8 gap-1.5 px-2 text-ink-muted hover:text-ink">
        <Link to="/" aria-label="back-to-projects">
          <ChevronLeft className="h-4 w-4" /> Projets
        </Link>
      </Button>
      <Hairline orientation="vertical" className="h-5" />
      <div className="flex items-center gap-2">
        <span className="font-display text-base font-medium text-ink">
          {projectName ?? 'Projet'}
        </span>
        <CodeTag>{projectId}</CodeTag>
      </div>

      <Hairline orientation="vertical" className="h-5" />
      <div className="flex items-center gap-2 text-xs">
        <span
          className="inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-[11px] font-medium text-green-700 bg-green-500/10"
          aria-label="job-status"
        >
          <Check className="h-3 w-3" /> Terminé
        </span>
        {elapsed != null && (
          <span
            className="font-mono tabular-nums text-ink-muted"
            aria-label="elapsed-time"
          >
            {Math.round(elapsed)} s
          </span>
        )}
        <Dialog>
          <DialogTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 text-ink-muted hover:text-ink"
              aria-label="open-journal"
            >
              <ClipboardList className="h-3.5 w-3.5" />
              Journal
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Journal du traitement</DialogTitle>
              <DialogDescription>
                Étapes du pipeline et durées telles que rapportées par le worker.
              </DialogDescription>
            </DialogHeader>
            <ProgressPanel messages={progressMessages} status="completed" />
          </DialogContent>
        </Dialog>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          disabled={count === 0}
          onClick={() => dispatch({ type: 'CLEAR_FILTERS' })}
          className={cn(
            'h-8 gap-1.5 px-2 text-ink-muted',
            count > 0 && 'text-ink hover:bg-signal/10 hover:text-ink',
          )}
          aria-label="reset-filters"
        >
          <X className="h-4 w-4" />
          Réinitialiser
          {count > 0 && (
            <Pastille tone="signal" size="sm" className="ml-1">
              {count}
            </Pastille>
          )}
        </Button>

        <div className="relative group">
          <Button
            variant="default"
            size="sm"
            className="h-8 gap-1.5 px-3"
          >
            <Download className="h-4 w-4" />
            Export
          </Button>
          <div
            className={cn(
              'absolute right-0 top-full z-20 mt-1 min-w-[180px] rounded-lg border border-hair bg-popover p-1 shadow-floating',
              'pointer-events-none opacity-0 transition-opacity',
              'group-hover:pointer-events-auto group-hover:opacity-100 focus-within:pointer-events-auto focus-within:opacity-100',
            )}
            role="menu"
            aria-label="export-menu"
          >
            <button
              type="button"
              role="menuitem"
              onClick={onExportGeoPackage}
              className="flex w-full items-center rounded-sm px-2 py-1.5 text-left text-sm text-ink hover:bg-secondary"
            >
              GeoPackage (.gpkg)
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={onExportCsvZip}
              className="flex w-full items-center rounded-sm px-2 py-1.5 text-left text-sm text-ink hover:bg-secondary"
            >
              CSV (.zip)
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
