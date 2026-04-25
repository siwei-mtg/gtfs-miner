/**
 * TableListSidebar — rail gauche du dashboard.  Mode rail : 6 pastilles
 * A–F empilées verticalement (48 px de large).  Au clic sur une pastille,
 * un flyout s'ouvre à droite, listant les tables du groupe.
 *
 *   ┌──┐  ╭──── flyout (A) ────╮
 *   │A ├──┤ A_1  Arrêts génér. │
 *   │B │  │ A_2  Arrêts physiq.│
 *   │C │  ╰────────────────────╯
 *   │D │
 *   │E │
 *   │F │
 *   └──┘
 *
 * La pastille signale un filtre actif sur le groupe avec un ring amber.
 */
import { useEffect, useRef, useState } from "react"

import { Pastille } from "@/components/atoms/Pastille"
import { TableSidebarItem } from "@/components/molecules/TableSidebarItem"
import { isTableFiltered, useDashboardSync } from "@/hooks/useDashboardSync"
import { cn } from "@/lib/utils"

interface TableDef {
  id: string
  code: string
  name: string
}

interface GroupDef {
  letter: string
  label: string
  tables: TableDef[]
}

export const SIDEBAR_GROUPS: GroupDef[] = [
  {
    letter: "A",
    label: "Arrêts",
    tables: [
      { id: "a1", code: "A_1", name: "Arrêts génériques" },
      { id: "a2", code: "A_2", name: "Arrêts physiques" },
    ],
  },
  {
    letter: "B",
    label: "Lignes",
    tables: [
      { id: "b1", code: "B_1", name: "Lignes" },
      { id: "b2", code: "B_2", name: "Sous-lignes" },
    ],
  },
  {
    letter: "C",
    label: "Courses",
    tables: [
      { id: "c1", code: "C_1", name: "Courses" },
      { id: "c2", code: "C_2", name: "Itinéraire" },
      { id: "c3", code: "C_3", name: "Itinéraire arc" },
    ],
  },
  {
    letter: "D",
    label: "Calendrier",
    tables: [
      { id: "d1", code: "D_1", name: "Service dates" },
      { id: "d2", code: "D_2", name: "Service jourtype" },
    ],
  },
  {
    letter: "E",
    label: "Passages",
    tables: [
      { id: "e1", code: "E_1", name: "Passage AG" },
      { id: "e4", code: "E_4", name: "Passage arc" },
    ],
  },
  {
    letter: "F",
    label: "Agrégats lignes",
    tables: [
      { id: "f1", code: "F_1", name: "Nb courses / ligne" },
      { id: "f2", code: "F_2", name: "Caract. sous-lignes" },
      { id: "f3", code: "F_3", name: "KCC lignes" },
      { id: "f4", code: "F_4", name: "KCC sous-lignes" },
    ],
  },
]

interface Props {
  activeTableId?: string | null
  onTableClick: (tableId: string) => void
  className?: string
}

export function TableListSidebar({ activeTableId, onTableClick, className }: Props) {
  const { state } = useDashboardSync()
  const [openGroup, setOpenGroup] = useState<string | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!openGroup) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenGroup(null)
    }
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpenGroup(null)
      }
    }
    window.addEventListener("keydown", onKey)
    window.addEventListener("mousedown", onClick)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener("mousedown", onClick)
    }
  }, [openGroup])

  const activeGroupLetter = openGroup
    ? openGroup
    : activeTableId
      ? SIDEBAR_GROUPS.find((g) =>
          g.tables.some((t) => t.id === activeTableId),
        )?.letter
      : null

  return (
    <div
      ref={rootRef}
      className={cn("relative flex h-full flex-col items-center gap-1 py-3", className)}
      data-testid="table-list-sidebar"
    >
      {SIDEBAR_GROUPS.map((group) => {
        const groupHasFilter = group.tables.some((t) => isTableFiltered(state, t.id))
        const isOpen = openGroup === group.letter
        const isActiveHere = activeGroupLetter === group.letter
        return (
          <div key={group.letter} className="relative">
            <button
              type="button"
              onClick={() => setOpenGroup(isOpen ? null : group.letter)}
              aria-expanded={isOpen}
              aria-label={`Groupe ${group.letter} — ${group.label}`}
              data-testid={`sidebar-group-${group.letter.toLowerCase()}`}
              className={cn(
                "group block rounded-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                "hover:bg-secondary",
                isActiveHere && "bg-secondary",
              )}
            >
              <Pastille
                tone={isOpen ? "signal" : isActiveHere ? "default" : "muted"}
                size="lg"
                className={cn(
                  "relative",
                  groupHasFilter && !isOpen && "ring-2 ring-signal ring-offset-1 ring-offset-paper",
                )}
              >
                {group.letter}
              </Pastille>
            </button>

            {isOpen && (
              <div
                role="menu"
                aria-label={`Tables du groupe ${group.letter}`}
                className={cn(
                  "absolute left-full top-0 z-40 ml-2 w-60",
                  "rounded-lg border border-hair bg-popover shadow-floating",
                  "animate-in fade-in-0 zoom-in-95 duration-150",
                )}
              >
                <div className="border-b border-hair px-3 py-2">
                  <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-ink-muted">
                    {group.letter} · {group.label}
                  </span>
                </div>
                <div className="flex flex-col gap-0.5 p-1">
                  {group.tables.map((t) => (
                    <TableSidebarItem
                      key={t.id}
                      id={t.id}
                      code={t.code}
                      name={t.name}
                      filtered={isTableFiltered(state, t.id)}
                      active={activeTableId === t.id}
                      onClick={() => {
                        onTableClick(t.id)
                        setOpenGroup(null)
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
