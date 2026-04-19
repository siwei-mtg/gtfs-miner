/**
 * table-filter-config.ts — Known filterable columns per result table (Task 38B).
 *
 * The backend `query_table` only honours ONE filter_field and ONE range_field
 * per request.  To keep the UI predictable we expose a primary enum column and
 * a primary numeric column per table; richer multi-column filtering can be
 * layered on top later without schema churn.
 */
import { getRouteTypeLabel } from './map-utils'

export interface FilterOption {
  value: string
  label: string
}

/** Primary enum column to render a MultiSelectFilter for, keyed by table short key. */
export const PRIMARY_ENUM_FIELD: Record<string, string> = {
  b1: 'route_type',
  b2: 'direction_id',
  c1: 'direction_id',
  d1: 'Type_Jour',
  d2: 'Type_Jour',
  e1: 'type_jour',
  e4: 'type_jour',
  f1: 'type_jour',
  f2: 'Type_Jour',
  f3: 'type_jour',
  f4: 'type_jour',
}

/** Primary numeric column to render a RangeFilter for, keyed by table short key. */
export const PRIMARY_NUMERIC_FIELD: Record<string, string> = {
  e1: 'nb_passage',
  e4: 'nb_passage',
  f1: 'nb_course',
  f3: 'kcc',
  f4: 'kcc',
}

/**
 * Hardcoded option list for enums whose domain is fixed by the GTFS spec.
 * For project-local enums (type_jour) we fall back to deriving options from
 * the rows the table already fetched.
 */
const ROUTE_TYPE_VALUES = ['0', '1', '2', '3', '4', '5', '6', '7', '11', '12']
const DIRECTION_ID_VALUES = ['0', '1', '999']

export function getEnumOptions(
  field: string,
  derivedValues: Array<string | number | null | undefined>,
): FilterOption[] {
  if (field === 'route_type') {
    return ROUTE_TYPE_VALUES.map((v) => ({ value: v, label: `${v} · ${getRouteTypeLabel(v)}` }))
  }
  if (field === 'direction_id') {
    return DIRECTION_ID_VALUES.map((v) => ({
      value: v,
      label: v === '0' ? '0 · Aller' : v === '1' ? '1 · Retour' : '999 · Inconnu',
    }))
  }
  // Generic: derive from the rows we already fetched.
  const distinct = Array.from(
    new Set(
      derivedValues
        .filter((v): v is string | number => v != null)
        .map((v) => String(v)),
    ),
  ).sort()
  return distinct.map((v) => ({ value: v, label: v }))
}

/** Map an enum field to the corresponding global `FilterState` key, if any. */
export const ENUM_FIELD_TO_FILTER_STATE_KEY: Record<string, 'routeTypes' | 'ligneIds' | 'agIds'> = {
  route_type: 'routeTypes',
  id_ligne_num: 'ligneIds',
  id_ag_num: 'agIds',
}
