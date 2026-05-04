/**
 * KpiRibbon — bandeau horizontal de 4 KPI éditoriaux sous le header du dashboard.
 *
 *   ▪ NB LIGNES         ▪ NB ARRÊTS        ▪ NB COURSES       ▪ KCC TOTAL
 *     12 / 42             238 / 1 204        1 250 / 8 473      6,3k / 41,5k
 *
 * Chaque cellule est un EditorialStat : label mini-caps en haut, valeur
 * Fraunces en display au-dessous, ratio 3:1 — signature data-journalism.
 *
 * Lorsqu'un filtre global est actif (routeTypes / ligneIds / agIds), on
 * affiche `filtré / base` : la valeur de gauche reflète le contexte courant,
 * celle de droite la même métrique sans aucun de ces filtres (mais sous le
 * jour_type courant — qui reste la baseline du dashboard).  Sans filtre on
 * n'affiche qu'une seule valeur, comme avant.
 *
 * Coût : deux appels parallèles seulement quand un filtre est posé ; sinon
 * un seul (la "base" est la valeur affichée).
 */
import { useEffect, useState } from "react"
import { Route, MapPin, Activity, Gauge } from "lucide-react"

import { getKpis, type FilterContext, type KpiResponse } from "@/api/client"
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

function formatLocale(n: number): string {
  return new Intl.NumberFormat("fr-FR").format(n)
}

export function KpiRibbon({ projectId, className }: Props) {
  const { state } = useDashboardSync()
  const [filtered, setFiltered] = useState<KpiResponse | null>(null)
  const [base, setBase] = useState<KpiResponse | null>(null)
  const [loading, setLoading] = useState(true)

  // Stable serialisations so the effect doesn't refire on identical arrays.
  const routeTypesKey = state.routeTypes.join(",")
  const ligneIdsKey = state.ligneIds.join(",")
  const agIdsKey = state.agIds.join(",")
  const isFiltered =
    state.routeTypes.length > 0 ||
    state.ligneIds.length > 0 ||
    state.agIds.length > 0

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    const ctx: FilterContext = {
      routeTypes: state.routeTypes,
      ligneIds: state.ligneIds,
      agIds: state.agIds,
    }

    // Always fetch the filtered snapshot.  Only fetch the base in parallel
    // when a filter is actually active — otherwise the two would be equal
    // and we'd burn a round-trip.
    const filteredPromise = getKpis(projectId, state.jourType, ctx)
    const basePromise = isFiltered
      ? getKpis(projectId, state.jourType)
      : Promise.resolve(null as KpiResponse | null)

    Promise.all([filteredPromise, basePromise])
      .then(([f, b]) => {
        if (cancelled) return
        setFiltered(f)
        // When unfiltered, mirror the single-fetch result into base so the
        // single-value rendering path can read either source.
        setBase(b ?? f)
      })
      .catch((err) => {
        if (cancelled) return
        console.error("getKpis failed:", err)
        setFiltered(null)
        setBase(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, state.jourType, routeTypesKey, ligneIdsKey, agIdsKey])

  return (
    <div
      data-testid="kpi-ribbon"
      data-filtered={isFiltered ? "true" : "false"}
      className={cn(
        "grid grid-cols-4 divide-x divide-hair bg-card",
        className,
      )}
    >
      <Cell
        label="Lignes"
        filteredValue={filtered?.nb_lignes ?? null}
        baseValue={base?.nb_lignes ?? null}
        formatter={formatLocale}
        showFraction={isFiltered}
        icon={<Route className="h-3 w-3" />}
        loading={loading}
      />
      <Cell
        label="Arrêts"
        filteredValue={filtered?.nb_arrets ?? null}
        baseValue={base?.nb_arrets ?? null}
        formatter={formatLocale}
        showFraction={isFiltered}
        icon={<MapPin className="h-3 w-3" />}
        loading={loading}
      />
      <Cell
        label="Courses"
        filteredValue={filtered?.nb_courses ?? null}
        baseValue={base?.nb_courses ?? null}
        formatter={formatLocale}
        showFraction={isFiltered}
        icon={<Activity className="h-3 w-3" />}
        loading={loading}
      />
      <Cell
        label="KCC total"
        filteredValue={filtered?.kcc_total ?? null}
        baseValue={base?.kcc_total ?? null}
        formatter={formatCompact}
        showFraction={isFiltered}
        icon={<Gauge className="h-3 w-3" />}
        loading={loading}
      />
    </div>
  )
}

interface CellProps {
  label: string
  filteredValue: number | null
  baseValue: number | null
  formatter: (n: number) => string
  showFraction: boolean
  icon: React.ReactNode
  loading: boolean
}

function Cell({
  label,
  filteredValue,
  baseValue,
  formatter,
  showFraction,
  icon,
  loading,
}: CellProps) {
  const testid = `kpi-${label.toLowerCase().replace(/\s+/g, "-")}`
  // Compose the displayed value once.  When filtered, render "X / Y" with
  // the base value muted; otherwise a single value.  The "—" placeholder
  // covers the loading / error path so the layout doesn't jump.
  const value: React.ReactNode = (() => {
    if (filteredValue === null) return "—"
    const f = formatter(filteredValue)
    if (!showFraction || baseValue === null) return f
    const b = formatter(baseValue)
    return (
      <span data-testid={`${testid}-fraction`}>
        <span>{f}</span>
        <span className="text-ink-muted"> / {b}</span>
      </span>
    )
  })()

  return (
    <div className="px-6 py-3" data-testid={testid}>
      <EditorialStat
        icon={icon}
        label={label}
        value={value}
        loading={loading}
        size="md"
      />
    </div>
  )
}
