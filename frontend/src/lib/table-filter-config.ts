/**
 * table-filter-config.ts — Cross-pane filter routing for dashboard charts.
 *
 * Since Task 38C the table filtering UI itself moved into per-header
 * Excel-style popovers (see `ColumnFilterPopover`).  This module now only
 * carries the metadata that ties dashboard chart selections (route_type,
 * id_ligne_num, id_ag_num) to the corresponding column on each result table.
 *
 * Responsibilities:
 *   - EXTERNAL_FILTER_COLUMNS: which column of each table receives chart-driven
 *     filter values (so a click on a route_type pie pre-fills the route_type
 *     column popover when the user opens table B_1).
 *   - ENUM_FIELD_TO_FILTER_STATE_KEY: reverse map used when ResultTable lifts
 *     a popover change back into the global FilterState context.
 *   - getRouteTypeLabel / getDirectionIdLabel: GTFS-spec value labelling for
 *     popover items (so the user sees "Bus" instead of just "3").
 */
import { getRouteTypeLabel } from './map-utils'
import type { ColumnDataType } from '@/types/api'

export interface FilterOption {
  value: string
  label: string
}

/**
 * Force certain ID-like columns to render as ``enum`` (cocher des valeurs)
 * regardless of the backend's column_meta type.
 *
 * The backend marks any Integer column ``numeric`` (range inputs only), but
 * for canonical IDs the user needs an enum picker — searching by stop name or
 * line number is the natural workflow.  The /distinct endpoint paginates so
 * even high-cardinality lists stay usable.
 */
export const COLUMN_TYPE_OVERRIDES: Record<string, ColumnDataType> = {
  id_ag_num: 'enum',
  id_ag_num_a: 'enum',
  id_ag_num_b: 'enum',
  id_ag_num_debut: 'enum',
  id_ag_num_terminus: 'enum',
  id_ligne_num: 'enum',
  route_type: 'enum',
  direction_id: 'enum',
}

/**
 * @deprecated since the cross-pane sync moved to /resolve + APPLY_RESOLVED.
 * Kept for any future "chart click → primary column chip" feature.  No
 * production code path reads this anymore.
 *
 * For each table that participates in the dashboard's filter sync, the column
 * whose values the global FilterState pushes into.  Tables not listed here
 * still have the per-column filter UI — they just don't reflect chart clicks.
 */
export const EXTERNAL_FILTER_COLUMNS: Record<string, string> = {
  b1: 'route_type',
  b2: 'id_ligne_num',
  e1: 'id_ag_num',
  e4: 'id_ag_num',
}

/**
 * Frontend mirror of which canonical (cross-pane) columns each result table
 * actually carries.  Source of truth: backend/app/models/result.py.
 *
 * Used by:
 *   - useDashboardSync.isTableFiltered → decide which sidebar pellets light up.
 *     A table only "lights up" for state.routeTypes if it actually has the
 *     route_type column.  Prevents the misleading mark on E_1/E_4 when the
 *     user filters B_1/B_2 (E tables can't be filtered by line ID without a
 *     cross-table JOIN, which is out of scope today).
 *   - TablePopup.contextFilters → AND-merge state.ligneIds / .routeTypes /
 *     .agIds into the table fetch only for columns the target actually has.
 *
 * Keep in sync if a model gains/loses one of these columns.
 */
export const TABLE_COLUMNS: Record<string, ReadonlySet<string>> = {
  a1: new Set(['id_ag_num']),
  a2: new Set(['id_ag_num']),
  b1: new Set(['id_ligne_num', 'route_type']),
  b2: new Set(['id_ligne_num', 'sous_ligne']),
  c1: new Set(['id_ligne_num', 'sous_ligne']),
  c2: new Set(['id_ligne_num', 'sous_ligne', 'id_ag_num']),
  c3: new Set(['id_ligne_num', 'sous_ligne']),
  d1: new Set([]),
  d2: new Set(['id_ligne_num']),
  e1: new Set(['id_ag_num']),
  e4: new Set([]),
  f1: new Set(['id_ligne_num']),
  f2: new Set(['id_ligne_num', 'sous_ligne']),
  f3: new Set(['id_ligne_num']),
  f4: new Set(['id_ligne_num', 'sous_ligne']),
}

/** Reverse: column name → which FilterState slot it lifts changes into. */
export const ENUM_FIELD_TO_FILTER_STATE_KEY: Record<string, 'routeTypes' | 'ligneIds' | 'agIds'> = {
  route_type: 'routeTypes',
  id_ligne_num: 'ligneIds',
  id_ag_num: 'agIds',
}

const ROUTE_TYPE_VALUES = ['0', '1', '2', '3', '4', '5', '6', '7', '11', '12']
const DIRECTION_ID_LABELS: Record<string, string> = {
  '0': 'Aller',
  '1': 'Retour',
  '999': 'Inconnu',
}

/**
 * Display label for one distinct value of a known column.  Returns the raw
 * value as a fallback so unknown columns stay informative.  Used by the
 * column-filter popover to render "Bus" rather than "3".
 */
export function getColumnValueLabel(column: string, value: unknown): string {
  if (value === null || value === undefined) return '(vide)'
  const raw = String(value)
  if (column === 'route_type') {
    return ROUTE_TYPE_VALUES.includes(raw) ? `${raw} · ${getRouteTypeLabel(raw)}` : raw
  }
  if (column === 'direction_id') {
    return DIRECTION_ID_LABELS[raw] ? `${raw} · ${DIRECTION_ID_LABELS[raw]}` : raw
  }
  return raw
}
