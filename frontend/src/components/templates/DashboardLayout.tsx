/**
 * DashboardLayout — squelette 3 zones, carte comme héros.
 *
 *   ┌──────────────── header (48 px) ──────────────────┐
 *   ├──────────────── KPI ribbon (64 px) ──────────────┤
 *   ├──┬───────────────────────────────────────────────┤
 *   │  │                                               │
 *   │R │           M A P   (relative, plein-cadre)     │
 *   │A │                                               │
 *   │I │                               ╭─ card ──────╮ │
 *   │L │                               │  charts     │ │
 *   │  │                               ╰─────────────╯ │
 *   └──┴───────────────────────────────────────────────┘
 *    48                                   right:16 width:320
 *
 * Breakpoints :
 *   ≥ 1024 px : layout complet
 *   <  1024 px : la carte flottante se cache (à implémenter en v2)
 */
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

interface DashboardLayoutProps {
  header: ReactNode
  kpiRibbon?: ReactNode
  sidebar: ReactNode
  map: ReactNode
  rightPanel: ReactNode
  /** Rendu en plein écran par-dessus tout le layout (e.g. TablePopup). */
  overlay?: ReactNode
  className?: string
}

export function DashboardLayout({
  header,
  kpiRibbon,
  sidebar,
  map,
  rightPanel,
  overlay,
  className,
}: DashboardLayoutProps) {
  return (
    <div
      className={cn(
        "flex h-[100svh] w-full flex-col bg-paper",
        className,
      )}
      data-testid="dashboard-layout"
    >
      <header className="shrink-0 border-b border-hair bg-card">
        {header}
      </header>
      {kpiRibbon && (
        <div className="shrink-0 border-b border-hair">
          {kpiRibbon}
        </div>
      )}
      <div className="relative flex min-h-0 flex-1">
        <aside
          className="flex shrink-0 w-12 flex-col border-r border-hair bg-card"
          data-testid="dashboard-sidebar"
        >
          {sidebar}
        </aside>
        <section
          className="relative min-w-0 flex-1 overflow-hidden"
          data-testid="dashboard-map"
        >
          <div className="absolute inset-0">{map}</div>
          <aside
            className={cn(
              "absolute right-4 top-4 bottom-4 w-80 z-10",
              "hidden lg:flex flex-col overflow-hidden",
              "rounded-xl border border-hair bg-card/95 shadow-floating backdrop-blur-sm",
            )}
            data-testid="dashboard-right"
          >
            {rightPanel}
          </aside>
        </section>
      </div>
      {overlay}
    </div>
  )
}
