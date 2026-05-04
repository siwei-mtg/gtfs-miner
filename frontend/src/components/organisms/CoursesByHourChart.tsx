/**
 * CoursesByHourChart — 24-bucket hourly bar chart. Clicking a bar toggles
 * the hour in FilterState.hoursSelected so downstream tables (F_1, E_1, E_4)
 * can narrow to that time window.
 *
 * Re-queries whenever jour_type or route_types change.
 */
import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { getCoursesByHour, type CoursesByHourRow } from '@/api/client'
import { useDashboardSync } from '@/hooks/useDashboardSync'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Props {
  projectId: string
}

export function CoursesByHourChart({ projectId }: Props) {
  const { state, dispatch } = useDashboardSync()
  const [rows, setRows] = useState<CoursesByHourRow[]>([])
  const [loading, setLoading] = useState(true)

  // Stable serialisations so the effect's dep array stays array-equality-safe.
  const routeTypesKey = state.routeTypes.join(',')
  const ligneIdsKey = state.ligneIds.join(',')
  const agIdsKey = state.agIds.join(',')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getCoursesByHour(projectId, state.jourType, {
      routeTypes: state.routeTypes,
      ligneIds: state.ligneIds,
      agIds: state.agIds,
    })
      .then((res) => {
        if (!cancelled) setRows(res.rows)
      })
      .catch((err) => console.error('getCoursesByHour failed:', err))
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, state.jourType, routeTypesKey, ligneIdsKey, agIdsKey])

  return (
    <Card data-testid="chart-courses-by-hour" className="border-0 shadow-none">
      <CardHeader className="py-2">
        <CardTitle className="text-sm font-medium">Courses par heure de départ</CardTitle>
      </CardHeader>
      <CardContent className="h-40 p-2">
        {loading && rows.length === 0 ? (
          <div className="h-full w-full animate-pulse rounded bg-muted/50" aria-hidden />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="heure" tick={{ fontSize: 10 }} interval={1} />
              <YAxis tick={{ fontSize: 10 }} width={32} />
              <Tooltip
                formatter={(v) => `${Number(v)} courses`}
                labelFormatter={(h) => `${h}h`}
              />
              <Bar
                dataKey="nb_courses"
                cursor="pointer"
                onClick={(entry: { payload?: { heure?: number } } | { heure?: number }) => {
                  const h = 'payload' in entry && entry.payload
                    ? entry.payload.heure
                    : (entry as { heure?: number }).heure
                  if (h !== undefined) dispatch({ type: 'TOGGLE_HOUR', payload: h })
                }}
              >
                {rows.map((entry) => (
                  <Cell
                    key={entry.heure}
                    fill={
                      state.hoursSelected.length === 0 || state.hoursSelected.includes(entry.heure)
                        ? 'var(--primary, #7c3aed)'
                        : '#cbd5e1'
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
