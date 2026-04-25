/**
 * DashboardRightPanel — carte flottante qui héberge les 2 charts interactifs
 * du dashboard.  Les KPI ont migré vers KpiRibbon (bandeau sous le header).
 *
 *   ┌────────── CHARTS ──────────┐
 *   │  Courses × jour_type       │
 *   │  ─────────────────────────  │
 *   │  Courses × heure           │
 *   └────────────────────────────┘
 */
import { CoursesByJourTypeChart } from "@/components/organisms/CoursesByJourTypeChart"
import { CoursesByHourChart } from "@/components/organisms/CoursesByHourChart"
import { Hairline } from "@/components/atoms/Hairline"

interface Props {
  projectId: string
}

export function DashboardRightPanel({ projectId }: Props) {
  return (
    <div
      className="flex h-full flex-col"
      data-testid="dashboard-right-panel"
    >
      <div className="flex-1 overflow-y-auto">
        <div className="p-3">
          <CoursesByJourTypeChart projectId={projectId} />
        </div>
        <Hairline />
        <div className="p-3">
          <CoursesByHourChart projectId={projectId} />
        </div>
      </div>
    </div>
  )
}
