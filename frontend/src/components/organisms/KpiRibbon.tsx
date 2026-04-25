/**
 * KpiRibbon — bandeau horizontal de 4 KPI éditoriaux sous le header du dashboard.
 *
 *   ▪ NB LIGNES         ▪ NB ARRÊTS        ▪ NB COURSES       ▪ KCC TOTAL
 *     42                  1 204              8 473              41,5k
 *
 * Chaque cellule est un EditorialStat : label mini-caps en haut, valeur
 * Fraunces en display au-dessous, ratio 3:1 — signature data-journalism.
 * Les valeurs se re-fetchent quand jour_type ou route_types changent.
 */
import { useEffect, useState } from "react"
import { Route, MapPin, Activity, Gauge } from "lucide-react"

import { getKpis, type KpiResponse } from "@/api/client"
import { EditorialStat } from "@/components/molecules/EditorialStat"
import { useDashboardSync } from "@/hooks/useDashboardSync"
import { cn } from "@/lib/utils"

interface Props {
  projectId: string
  className?: string
}

function formatCompact(n: number): string {
  if (n >= 10_000) {
    return new Intl.NumberFormat("fr-FR", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(n)
  }
  return new Intl.NumberFormat("fr-FR").format(n)
}

export function KpiRibbon({ projectId, className }: Props) {
  const { state } = useDashboardSync()
  const [kpis, setKpis] = useState<KpiResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const routeTypesKey = state.routeTypes.join(",")

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getKpis(projectId, state.jourType, state.routeTypes)
      .then((res) => {
        if (!cancelled) setKpis(res)
      })
      .catch((err) => {
        console.error("getKpis failed:", err)
        if (!cancelled) setKpis(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, state.jourType, routeTypesKey])

  return (
    <div
      data-testid="kpi-ribbon"
      className={cn(
        "grid grid-cols-4 divide-x divide-hair bg-card",
        className,
      )}
    >
      <Cell
        label="Lignes"
        value={kpis?.nb_lignes ?? null}
        icon={<Route className="h-3 w-3" />}
        loading={loading}
      />
      <Cell
        label="Arrêts"
        value={kpis?.nb_arrets ?? null}
        icon={<MapPin className="h-3 w-3" />}
        loading={loading}
      />
      <Cell
        label="Courses"
        value={kpis?.nb_courses ?? null}
        icon={<Activity className="h-3 w-3" />}
        loading={loading}
      />
      <Cell
        label="KCC total"
        value={kpis ? formatCompact(kpis.kcc_total) : null}
        icon={<Gauge className="h-3 w-3" />}
        loading={loading}
      />
    </div>
  )
}

function Cell({
  label,
  value,
  icon,
  loading,
}: {
  label: string
  value: string | number | null
  icon: React.ReactNode
  loading: boolean
}) {
  return (
    <div
      className="px-6 py-3"
      data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <EditorialStat
        icon={icon}
        label={label}
        value={value ?? "—"}
        loading={loading}
        size="md"
      />
    </div>
  )
}
