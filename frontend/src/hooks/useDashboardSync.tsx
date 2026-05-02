/**
 * useDashboardSync — global filter state shared between Map, Charts, KPIs,
 * and Table panels on the Dashboard page.
 *
 * FilterState lives in a React Context so each pane can dispatch changes and
 * subscribe to others' changes without prop-drilling:
 *   - Map pie-click         → TOGGLE_AG_ID          → Charts + KPI + Tables re-query
 *   - jour_type bar click   → SET_JOUR_TYPE         → everything re-queries
 *   - hour bar click        → TOGGLE_HOUR           → (C_1-based) table filters
 *   - Table filter UI       → SET_ROUTE_TYPES / SET_LIGNE_IDS
 */
import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react'

import type { ColumnFilter } from '@/types/api'

/** Composite key identifying a sous-ligne (sub-line direction/variant). */
export interface SousLigneKey {
  id_ligne_num: number
  sous_ligne: string
}

export interface FilterState {
  /** Active jour_type (required everywhere — maps / charts / tables). */
  jourType: number
  /** Initial jour_type recorded at provider boot so the header badge can tell
   *  "user customised this" from "still on the default". */
  initialJourType: number
  /** route_type values (as strings: "0", "3", …) the user has opted into. */
  routeTypes: string[]
  /** id_ligne_num values the user has opted into. */
  ligneIds: number[]
  /** Sous-ligne pairs the user has opted into.  Independent of ligneIds —
   *  both filters AND together when sent to the map endpoints. */
  sousLigneKeys: SousLigneKey[]
  /** id_ag_num values the user has opted into (map pie-chart click selection). */
  agIds: number[]
  /** Hours of day (0..23) the user has opted into via the hourly bar chart. */
  hoursSelected: number[]
  /** Per-table column filter cache (keyed by tableId, then column).  Survives
   *  Dialog/ResultTable unmount so filters reappear when the user reopens the
   *  same table.  Also feeds `isTableFiltered` so non-mapped column filters
   *  light up the sidebar ring. */
  tableFilters: Record<string, Record<string, ColumnFilter>>
}

export type FilterAction =
  | { type: 'SET_JOUR_TYPE'; payload: number }
  | { type: 'TOGGLE_ROUTE_TYPE'; payload: string }
  | { type: 'SET_ROUTE_TYPES'; payload: string[] }
  | { type: 'SET_LIGNE_IDS'; payload: number[] }
  | { type: 'SET_SOUS_LIGNE_KEYS'; payload: SousLigneKey[] }
  | { type: 'TOGGLE_AG_ID'; payload: number; shift: boolean }
  | { type: 'SET_AG_IDS'; payload: number[] }
  | { type: 'TOGGLE_HOUR'; payload: number }
  | { type: 'SET_TABLE_FILTERS'; tableId: string; payload: Record<string, ColumnFilter> }
  | { type: 'CLEAR_FILTERS' }

function toggleInArray<T>(arr: T[], value: T): T[] {
  return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value]
}

/**
 * Shallow equality on ordered arrays of primitives.  Used by the SET_*
 * reducer cases to avoid returning a fresh state reference when the caller
 * dispatches with identical content — without this, a two-way sync path
 * (ResultTable ↔ context ↔ ResultTable) re-fires every render and React
 * throws "Maximum update depth exceeded" (see commit 98decec for history).
 */
function sameArray<T>(a: readonly T[], b: readonly T[]): boolean {
  if (a === b) return true
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false
  return true
}

/** Same-content check for SousLigneKey arrays (objects with two scalar fields). */
function sameSousLigneKeys(a: readonly SousLigneKey[], b: readonly SousLigneKey[]): boolean {
  if (a === b) return true
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    if (a[i].id_ligne_num !== b[i].id_ligne_num || a[i].sous_ligne !== b[i].sous_ligne) {
      return false
    }
  }
  return true
}

/** Shallow value equality for one ColumnFilter clause. */
function sameColumnFilter(a: ColumnFilter, b: ColumnFilter): boolean {
  if (a.kind !== b.kind) return false
  if (a.kind === 'in' && b.kind === 'in') return sameArray(a.values, b.values)
  if (a.kind === 'range' && b.kind === 'range') return a.min === b.min && a.max === b.max
  if (a.kind === 'contains' && b.kind === 'contains') return a.term === b.term
  return false
}

/** Equality on Record<column, ColumnFilter> — used by the SET_TABLE_FILTERS
 *  reducer to suppress no-op dispatches and short-circuit re-renders. */
function sameColumnFilterMap(
  a: Record<string, ColumnFilter>,
  b: Record<string, ColumnFilter>,
): boolean {
  const ka = Object.keys(a)
  const kb = Object.keys(b)
  if (ka.length !== kb.length) return false
  for (const k of ka) {
    if (!(k in b)) return false
    if (!sameColumnFilter(a[k], b[k])) return false
  }
  return true
}

export function dashboardSyncReducer(state: FilterState, action: FilterAction): FilterState {
  switch (action.type) {
    case 'SET_JOUR_TYPE':
      if (state.jourType === action.payload) return state
      return { ...state, jourType: action.payload }

    case 'TOGGLE_ROUTE_TYPE':
      return { ...state, routeTypes: toggleInArray(state.routeTypes, action.payload) }

    case 'SET_ROUTE_TYPES':
      if (sameArray(state.routeTypes, action.payload)) return state
      return { ...state, routeTypes: action.payload }

    case 'SET_LIGNE_IDS':
      if (sameArray(state.ligneIds, action.payload)) return state
      return { ...state, ligneIds: action.payload }

    case 'SET_SOUS_LIGNE_KEYS':
      if (sameSousLigneKeys(state.sousLigneKeys, action.payload)) return state
      return { ...state, sousLigneKeys: action.payload }

    case 'TOGGLE_AG_ID':
      if (action.shift) {
        return { ...state, agIds: toggleInArray(state.agIds, action.payload) }
      }
      // Plain click: replace with single selection, or clear if same AG is clicked twice.
      return {
        ...state,
        agIds:
          state.agIds.length === 1 && state.agIds[0] === action.payload ? [] : [action.payload],
      }

    case 'SET_AG_IDS':
      if (sameArray(state.agIds, action.payload)) return state
      return { ...state, agIds: action.payload }

    case 'TOGGLE_HOUR': {
      const next = toggleInArray(state.hoursSelected, action.payload)
      if (sameArray(state.hoursSelected, next)) return state
      return { ...state, hoursSelected: next }
    }

    case 'SET_TABLE_FILTERS': {
      const prev = state.tableFilters[action.tableId] ?? {}
      if (sameColumnFilterMap(prev, action.payload)) return state
      const nextMap = { ...state.tableFilters }
      if (Object.keys(action.payload).length === 0) {
        delete nextMap[action.tableId]
      } else {
        nextMap[action.tableId] = action.payload
      }
      return { ...state, tableFilters: nextMap }
    }

    case 'CLEAR_FILTERS':
      return {
        ...state,
        jourType: state.initialJourType,
        routeTypes: [],
        ligneIds: [],
        sousLigneKeys: [],
        agIds: [],
        hoursSelected: [],
        tableFilters: {},
      }

    default:
      return state
  }
}

/** Total number of independently-set filter dimensions — powers the reset badge. */
export function activeFilterCount(state: FilterState): number {
  let n = 0
  if (state.jourType !== state.initialJourType) n += 1
  if (state.routeTypes.length > 0) n += 1
  if (state.ligneIds.length > 0) n += 1
  if (state.sousLigneKeys.length > 0) n += 1
  if (state.agIds.length > 0) n += 1
  if (state.hoursSelected.length > 0) n += 1
  // Each table that carries local non-mapped filters counts once.  Even if a
  // table has multiple per-column filters, it's still one "filtered table".
  for (const cols of Object.values(state.tableFilters)) {
    if (Object.keys(cols).length > 0) n += 1
  }
  return n
}

/**
 * Tell the sidebar which table should show a funnel icon given the current
 * filters.  Mapping is taken straight from DASHBOARD_REFONTE_PLAN.md §
 * "筛选维度 → 表格 映射".
 */
const TABLES_AFFECTED: Record<
  keyof Omit<FilterState, 'jourType' | 'initialJourType' | 'tableFilters'> | 'jourType',
  string[]
> = {
  routeTypes: ['b1', 'b2', 'f1', 'f3', 'e1', 'e4'],
  ligneIds: ['b1', 'b2', 'f1', 'f3', 'e1', 'e4'],
  sousLigneKeys: ['b2', 'e1', 'e4'],
  agIds: ['a1', 'e1', 'e4'],
  hoursSelected: ['f1', 'e1', 'e4'],
  jourType: ['f1', 'f3', 'e1', 'e4'],
}

export function isTableFiltered(state: FilterState, tableId: string): boolean {
  if (state.routeTypes.length > 0 && TABLES_AFFECTED.routeTypes.includes(tableId)) return true
  if (state.ligneIds.length > 0 && TABLES_AFFECTED.ligneIds.includes(tableId)) return true
  if (state.sousLigneKeys.length > 0 && TABLES_AFFECTED.sousLigneKeys.includes(tableId)) return true
  if (state.agIds.length > 0 && TABLES_AFFECTED.agIds.includes(tableId)) return true
  if (state.hoursSelected.length > 0 && TABLES_AFFECTED.hoursSelected.includes(tableId)) return true
  if (state.jourType !== state.initialJourType && TABLES_AFFECTED.jourType.includes(tableId)) return true
  // Local per-table column filters (route_long_name etc.) — light up the ring
  // even when no mapped slot is set.
  const local = state.tableFilters[tableId]
  if (local && Object.keys(local).length > 0) return true
  return false
}

interface ContextValue {
  state: FilterState
  dispatch: Dispatch<FilterAction>
}

const DashboardSyncContext = createContext<ContextValue | null>(null)

export function DashboardSyncProvider({
  initialJourType,
  children,
}: {
  initialJourType: number
  children: ReactNode
}) {
  const [state, dispatch] = useReducer(dashboardSyncReducer, {
    jourType: initialJourType,
    initialJourType,
    routeTypes: [],
    ligneIds: [],
    sousLigneKeys: [],
    agIds: [],
    hoursSelected: [],
    tableFilters: {},
  })
  const value = useMemo(() => ({ state, dispatch }), [state])
  return <DashboardSyncContext.Provider value={value}>{children}</DashboardSyncContext.Provider>
}

export function useDashboardSync(): ContextValue {
  const ctx = useContext(DashboardSyncContext)
  if (!ctx) {
    throw new Error('useDashboardSync must be used inside <DashboardSyncProvider>')
  }
  return ctx
}
