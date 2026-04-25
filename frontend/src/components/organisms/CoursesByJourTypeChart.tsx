/**
 * CoursesByJourTypeChart — vertical bar chart of total courses per jour_type.
 * Clicking a bar dispatches SET_JOUR_TYPE, replacing the previous header
 * dropdown.  The bar corresponding to the current jour_type is highlighted.
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

import { getCoursesByJourType, type CoursesByJourTypeRow } from '@/api/client'
import { useDashboardSync } from '@/hooks/useDashboardSync'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Props {
  projectId: string
}

export function CoursesByJourTypeChart({ projectId }: Props) {
  const { state, dispatch } = useDashboardSync()
  const [rows, setRows] = useState<CoursesByJourTypeRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getCoursesByJourType(projectId)
      .then((res) => {
        if (!cancelled) {
          setRows(res.rows)
        }
      })
      .catch((err) => console.error('getCoursesByJourType failed:', err))
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [projectId])

  const chartData = rows.map((r) => ({
    jour_type: r.jour_type,
    // Horizontal bars → place pour le nom complet, on remplace juste les
    // underscores par des espaces pour la lecture.
    label: r.jour_type_name.replace(/_/g, ' '),
    nb_courses: r.nb_courses,
  }))

  // Hauteur dynamique : ~22 px par barre + marges, pour que tous les types
  // respirent quel que soit le nombre (1 à ~12 jour_types).
  const chartHeight = Math.max(160, chartData.length * 26 + 20)

  return (
    <Card data-testid="chart-courses-by-jour-type" className="border-0 shadow-none">
      <CardHeader className="py-2">
        <CardTitle className="text-[10px] font-medium uppercase tracking-[0.15em] text-ink-muted">
          Courses par type de jour
        </CardTitle>
      </CardHeader>
      <CardContent className="p-2" style={{ height: chartHeight }}>
        {loading && rows.length === 0 ? (
          <div className="h-full w-full animate-pulse rounded bg-muted/50" aria-hidden />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 2, right: 12, bottom: 2, left: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis
                type="category"
                dataKey="label"
                tick={{ fontSize: 10 }}
                width={110}
                interval={0}
              />
              <Tooltip formatter={(v) => `${Number(v)} courses`} />
              <Bar
                dataKey="nb_courses"
                cursor="pointer"
                onClick={(entry: { payload?: { jour_type?: number } } | { jour_type?: number }) => {
                  const jt = 'payload' in entry && entry.payload
                    ? entry.payload.jour_type
                    : (entry as { jour_type?: number }).jour_type
                  if (jt !== undefined) dispatch({ type: 'SET_JOUR_TYPE', payload: jt })
                }}
              >
                {chartData.map((entry) => (
                  <Cell
                    key={entry.jour_type}
                    fill={
                      entry.jour_type === state.jourType
                        ? 'var(--signal)'
                        : 'var(--hair)'
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
