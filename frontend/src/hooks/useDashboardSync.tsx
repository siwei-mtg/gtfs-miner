/**
 * useDashboardSync — global filter state shared between Map, Charts, and Table
 * panels on the Dashboard page (Task 39A).
 *
 * FilterState lives in a React Context so each pane can dispatch changes and
 * subscribe to others' changes without prop-drilling:
 *   - Map pie-click      → TOGGLE_AG_ID          → Charts + Table re-query
 *   - Chart sector click → TOGGLE_ROUTE_TYPE     → Map + Table re-query
 *   - Table filter UI    → SET_ROUTE_TYPES / SET_LIGNE_IDS
 */
import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react'

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

export type FilterAction =
  | { type: 'SET_JOUR_TYPE'; payload: number }
  | { type: 'TOGGLE_ROUTE_TYPE'; payload: string }
  | { type: 'SET_ROUTE_TYPES'; payload: string[] }
  | { type: 'SET_LIGNE_IDS'; payload: number[] }
  | { type: 'TOGGLE_AG_ID'; payload: number; shift: boolean }
  | { type: 'SET_AG_IDS'; payload: number[] }
  | { type: 'CLEAR_FILTERS' }

function toggleInArray<T>(arr: T[], value: T): T[] {
  return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value]
}

export function dashboardSyncReducer(state: FilterState, action: FilterAction): FilterState {
  switch (action.type) {
    case 'SET_JOUR_TYPE':
      if (state.jourType === action.payload) return state
      return { ...state, jourType: action.payload }

    case 'TOGGLE_ROUTE_TYPE':
      return { ...state, routeTypes: toggleInArray(state.routeTypes, action.payload) }

    case 'SET_ROUTE_TYPES':
      return { ...state, routeTypes: action.payload }

    case 'SET_LIGNE_IDS':
      return { ...state, ligneIds: action.payload }

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
      return { ...state, agIds: action.payload }

    case 'CLEAR_FILTERS':
      return { ...state, routeTypes: [], ligneIds: [], agIds: [] }

    default:
      return state
  }
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
    routeTypes: [],
    ligneIds: [],
    agIds: [],
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
