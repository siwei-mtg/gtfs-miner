/**
 * DashboardHeader — top bar specific to the dashboard view.
 *
 *   [← Projets]  [project id]  ·  [🔄 Réinitialiser (N)]  ·  [⚙️ Gérer]  ·  [📥 Export ▾]
 *
 * Replaces the generic AppHeader on the dashboard page so the dropdowns
 * (jour_type) that used to live here can be retired in favour of chart-based
 * filtering.
 */
import { Link } from 'react-router-dom'
import { ChevronLeft, Download, X } from 'lucide-react'

import { Button } from '@/components/atoms/button'
import { CodeTag } from '@/components/atoms/CodeTag'
import { Pastille } from '@/components/atoms/Pastille'
import { Hairline } from '@/components/atoms/Hairline'
import { activeFilterCount, useDashboardSync } from '@/hooks/useDashboardSync'
import { cn } from '@/lib/utils'

interface Props {
  projectId: string
  /** Display name for the project; falls back to the ID when the project
   *  schema has no human label yet. */
  projectName?: string
  /** Invoked when the user picks GeoPackage from the export dropdown. */
  onExportGeoPackage: () => void
  /** Invoked when the user picks CSV zip from the export dropdown. */
  onExportCsvZip: () => void
  className?: string
}

export function DashboardHeader({
  projectId,
  projectName,
  onExportGeoPackage,
  onExportCsvZip,
  className,
}: Props) {
  const { state, dispatch } = useDashboardSync()
  const count = activeFilterCount(state)

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
        <Link
          to={`/projects/${projectId}`}
          aria-label="open-project-management"
          title="Ouvrir la page de gestion du projet"
          className="transition-colors"
        >
          <CodeTag className="cursor-pointer hover:bg-signal/20 hover:text-ink">
            {projectId}
          </CodeTag>
        </Link>
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
