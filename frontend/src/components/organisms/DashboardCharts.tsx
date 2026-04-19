/**
 * DashboardCharts — 4-panel analytics view for a project (Task 37B).
 *
 * Charts:
 *   1. Répartition par mode — PieChart of route_type counts (B_1)
 *   2. Top 20 lignes par Nb courses — horizontal BarChart (F_1, jour_type filtered)
 *   3. Top 20 lignes par KCC — horizontal BarChart (F_3, jour_type filtered)
 *   4. Heure de pointe vs heure creuse — stacked BarChart (/charts/peak-offpeak)
 */
import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getPeakOffpeak, getTableData } from '@/api/client'
import type { FilterState } from '@/hooks/useDashboardSync'
import { ROUTE_TYPE_COLORS, getRouteTypeLabel } from '@/lib/map-utils'
import { cn } from '@/lib/utils'

interface Props {
  projectId: string
  jourType: number
  filters?: Partial<FilterState>
  className?: string
  /** Fired when the user clicks a Pie slice; the Dashboard maps it to
   *  TOGGLE_ROUTE_TYPE so the other panels re-filter. */
  onRouteTypeClick?: (routeType: string) => void
}

interface RouteTypeDatum { name: string; value: number; color: string; route_type: string }
interface LigneDatum     { name: string; value: number; id_ligne_num: number }
interface PeakDatum      { name: string; id_ag_num: number; peak: number; offpeak: number }

/**
 * Server cap on /tables is 200 rows (`result_query.query_table`).  We pull the
 * full cap, then filter / sort / slice client-side.  Task 38A will add proper
 * server-side `filter_field`/`filter_values` so IDFM-scale networks can
 * target type_jour without risking truncation.
 */
const MAX_ROWS = 200

export function DashboardCharts({ projectId, jourType, filters, className, onRouteTypeClick }: Props) {
  const [routeTypeData, setRouteTypeData] = useState<RouteTypeDatum[]>([])
  const [topCourses, setTopCourses] = useState<LigneDatum[]>([])
  const [topKcc, setTopKcc] = useState<LigneDatum[]>([])
  const [peakOffpeak, setPeakOffpeak] = useState<PeakDatum[]>([])

  const filtersKey = useMemo(() => JSON.stringify(filters ?? {}), [filters])

  useEffect(() => {
    let cancelled = false
    const selectedRouteTypes = filters?.routeTypes ?? []
    const selectedLigneIds = filters?.ligneIds ?? []
    const selectedAgIds = filters?.agIds ?? []

    async function load() {
      const [b1, f1, f3, peak] = await Promise.all([
        getTableData(projectId, 'b1', { skip: 0, limit: MAX_ROWS }),
        getTableData(projectId, 'f1', {
          skip: 0, limit: MAX_ROWS, sort_by: 'nb_course', sort_order: 'desc',
        }),
        getTableData(projectId, 'f3', {
          skip: 0, limit: MAX_ROWS, sort_by: 'kcc', sort_order: 'desc',
        }),
        getPeakOffpeak(projectId, jourType),
      ])
      if (cancelled) return

      // Pie: COUNT B_1 rows per route_type, optionally constrained by filter.
      const modeCounts = new Map<string, number>()
      for (const row of b1.rows as Array<{ route_type: number | null }>) {
        const rt = row.route_type == null ? 'default' : String(row.route_type)
        if (selectedRouteTypes.length > 0 && !selectedRouteTypes.includes(rt)) continue
        modeCounts.set(rt, (modeCounts.get(rt) ?? 0) + 1)
      }
      setRouteTypeData(
        Array.from(modeCounts, ([rt, value]) => ({
          name: getRouteTypeLabel(rt),
          value,
          color: ROUTE_TYPE_COLORS[rt] ?? ROUTE_TYPE_COLORS.default,
          route_type: rt,
        })),
      )

      type F1Row = { id_ligne_num: number; route_short_name: string | null; type_jour: number; nb_course: number }
      const top20 = (rows: F1Row[], valueKey: 'nb_course' | 'kcc') =>
        rows
          .filter((r) => r.type_jour === jourType)
          .filter((r) => selectedLigneIds.length === 0 || selectedLigneIds.includes(r.id_ligne_num))
          .sort((a, b) => (b as unknown as Record<string, number>)[valueKey] - (a as unknown as Record<string, number>)[valueKey])
          .slice(0, 20)

      const f1Top = top20(f1.rows as F1Row[], 'nb_course')
      setTopCourses(
        f1Top.map((r) => ({
          name: r.route_short_name ?? `#${r.id_ligne_num}`,
          value: r.nb_course,
          id_ligne_num: r.id_ligne_num,
        })),
      )

      type F3Row = F1Row & { kcc: number }
      const f3Top = top20(f3.rows as unknown as F3Row[], 'kcc')
      setTopKcc(
        f3Top.map((r) => ({
          name: r.route_short_name ?? `#${r.id_ligne_num}`,
          value: r.kcc,
          id_ligne_num: r.id_ligne_num,
        })),
      )

      const peakRows = peak.rows
        .filter((r) => selectedAgIds.length === 0 || selectedAgIds.includes(r.id_ag_num))
        .slice()
        .sort((a, b) => (b.peak_count + b.offpeak_count) - (a.peak_count + a.offpeak_count))
        .slice(0, 20)
      setPeakOffpeak(
        peakRows.map((r) => ({
          name: r.stop_name ?? `#${r.id_ag_num}`,
          id_ag_num: r.id_ag_num,
          peak: r.peak_count,
          offpeak: r.offpeak_count,
        })),
      )
    }

    void load()
    return () => { cancelled = true }
  }, [projectId, jourType, filtersKey])

  return (
    <div className={cn('grid grid-cols-1 xl:grid-cols-2 gap-4', className)}>
      <Card data-testid="chart-route-type">
        <CardHeader><CardTitle>Répartition par mode</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={routeTypeData}
                dataKey="value"
                nameKey="name"
                outerRadius={80}
                label
                onClick={(datum: { payload?: RouteTypeDatum } | RouteTypeDatum) => {
                  const rt = 'payload' in datum && datum.payload
                    ? datum.payload.route_type
                    : (datum as RouteTypeDatum).route_type
                  if (rt && onRouteTypeClick) onRouteTypeClick(rt)
                }}
              >
                {routeTypeData.map((entry) => (
                  <Cell
                    key={entry.route_type}
                    fill={entry.color}
                    cursor={onRouteTypeClick ? 'pointer' : 'default'}
                  />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card data-testid="chart-top-courses">
        <CardHeader><CardTitle>Top 20 lignes · Nb. courses</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={topCourses} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="value" fill="var(--primary, #7c3aed)" name="Nb. courses" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card data-testid="chart-top-kcc">
        <CardHeader><CardTitle>Top 20 lignes · KCC</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={topKcc} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#ec4899" name="KCC" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card data-testid="chart-peak-offpeak">
        <CardHeader><CardTitle>Heure de pointe vs creuse · Top 20 arrêts</CardTitle></CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={peakOffpeak}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={60} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="peak" stackId="a" fill="#ef4444" name="Heure de pointe" />
              <Bar dataKey="offpeak" stackId="a" fill="#94a3b8" name="Heure creuse" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}
