/**
 * useDashboardSync — Phase 2 GROUP C dashboard filter state (Task 39).
 *
 * This file currently exports just the `FilterState` shape so Task 37B
 * (DashboardCharts) and Task 38B (ResultTable filters) can type their props
 * consistently.  Task 39A adds the reducer, Provider, and the hook itself.
 */

export interface FilterState {
  /** Active jour_type (required everywhere — maps / charts / tables). */
  jourType: number
  /** route_type values (as strings: "0", "3", …) the user has opted into. */
  routeTypes: string[]
  /** id_ligne_num values the user has opted into. */
  ligneIds: number[]
  /** id_ag_num values the user has opted into (map pie-chart click selection). */
  agIds: number[]
}
