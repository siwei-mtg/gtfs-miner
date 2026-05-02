import { describe, it, expect } from 'vitest'
import {
  activeFilterCount,
  dashboardSyncReducer,
  isTableFiltered,
  type FilterState,
} from '@/hooks/useDashboardSync'

function freshState(overrides: Partial<FilterState> = {}): FilterState {
  return {
    jourType: 1,
    initialJourType: 1,
    routeTypes: [],
    ligneIds: [],
    sousLigneKeys: [],
    agIds: [],
    hoursSelected: [],
    tableFilters: {},
    ...overrides,
  }
}

describe('dashboardSyncReducer — TOGGLE_HOUR', () => {
  it('adds an hour to an empty selection', () => {
    const next = dashboardSyncReducer(freshState(), { type: 'TOGGLE_HOUR', payload: 8 })
    expect(next.hoursSelected).toEqual([8])
  })

  it('removes a previously-selected hour', () => {
    const s = freshState({ hoursSelected: [7, 8, 9] })
    const next = dashboardSyncReducer(s, { type: 'TOGGLE_HOUR', payload: 8 })
    expect(next.hoursSelected).toEqual([7, 9])
  })

  it('preserves reference when the sameArray guard triggers (defensive)', () => {
    // There is no code path that can produce an identical array through
    // TOGGLE_HOUR, but SET_ROUTE_TYPES / SET_LIGNE_IDS must; this covers
    // the contract that identical payloads do not break referential equality.
    const s = freshState({ routeTypes: ['3'] })
    const next = dashboardSyncReducer(s, { type: 'SET_ROUTE_TYPES', payload: ['3'] })
    expect(next).toBe(s)
  })
})

describe('dashboardSyncReducer — CLEAR_FILTERS', () => {
  it('resets every dimension including jourType back to initial and hoursSelected', () => {
    const s = freshState({
      jourType: 7,
      initialJourType: 1,
      routeTypes: ['0', '3'],
      ligneIds: [10, 11],
      agIds: [42],
      hoursSelected: [8, 9],
      tableFilters: { b2: { route_long_name: { kind: 'in', values: ['Ligne 1'] } } },
    })
    const next = dashboardSyncReducer(s, { type: 'CLEAR_FILTERS' })
    expect(next.jourType).toBe(1)
    expect(next.routeTypes).toEqual([])
    expect(next.ligneIds).toEqual([])
    expect(next.agIds).toEqual([])
    expect(next.hoursSelected).toEqual([])
    expect(next.tableFilters).toEqual({})
  })
})

describe('dashboardSyncReducer — SET_TABLE_FILTERS', () => {
  it('inserts a new per-table filter map', () => {
    const next = dashboardSyncReducer(freshState(), {
      type: 'SET_TABLE_FILTERS',
      tableId: 'b2',
      payload: { route_long_name: { kind: 'in', values: ['Ligne 1'] } },
    })
    expect(next.tableFilters).toEqual({
      b2: { route_long_name: { kind: 'in', values: ['Ligne 1'] } },
    })
  })

  it('returns the same state reference when payload is unchanged (no-op guard)', () => {
    const s = freshState({
      tableFilters: { b2: { route_long_name: { kind: 'in', values: ['Ligne 1'] } } },
    })
    const next = dashboardSyncReducer(s, {
      type: 'SET_TABLE_FILTERS',
      tableId: 'b2',
      payload: { route_long_name: { kind: 'in', values: ['Ligne 1'] } },
    })
    expect(next).toBe(s)
  })

  it('removes the tableId entry when payload is empty', () => {
    const s = freshState({
      tableFilters: { b2: { route_long_name: { kind: 'in', values: ['Ligne 1'] } } },
    })
    const next = dashboardSyncReducer(s, {
      type: 'SET_TABLE_FILTERS',
      tableId: 'b2',
      payload: {},
    })
    expect(next.tableFilters).toEqual({})
  })

  it('only mutates the targeted tableId, leaving others untouched', () => {
    const s = freshState({
      tableFilters: {
        b1: { route_short_name: { kind: 'in', values: ['L1'] } },
        b2: { route_long_name: { kind: 'in', values: ['Ligne 1'] } },
      },
    })
    const next = dashboardSyncReducer(s, {
      type: 'SET_TABLE_FILTERS',
      tableId: 'b2',
      payload: { route_long_name: { kind: 'in', values: ['Ligne 7'] } },
    })
    expect(next.tableFilters.b1).toBe(s.tableFilters.b1)
    expect(next.tableFilters.b2).toEqual({
      route_long_name: { kind: 'in', values: ['Ligne 7'] },
    })
  })
})

describe('activeFilterCount', () => {
  it('returns 0 when no filter is set', () => {
    expect(activeFilterCount(freshState())).toBe(0)
  })

  it('counts a custom jour_type', () => {
    expect(activeFilterCount(freshState({ jourType: 2, initialJourType: 1 }))).toBe(1)
  })

  it('counts each populated dimension once', () => {
    const s = freshState({
      jourType: 2,
      initialJourType: 1,
      routeTypes: ['3'],
      agIds: [42],
      hoursSelected: [8, 9],
    })
    expect(activeFilterCount(s)).toBe(4) // jourType + routeTypes + agIds + hoursSelected
  })

  it('counts each table with non-empty local filters', () => {
    const s = freshState({
      tableFilters: {
        b2: { route_long_name: { kind: 'in', values: ['Ligne 1'] } },
        e1: { id_ag_num: { kind: 'in', values: ['42'] } },
      },
    })
    expect(activeFilterCount(s)).toBe(2)
  })
})

describe('isTableFiltered', () => {
  it('marks F_1 as filtered when an hour is selected', () => {
    const s = freshState({ hoursSelected: [8] })
    expect(isTableFiltered(s, 'f1')).toBe(true)
    expect(isTableFiltered(s, 'b1')).toBe(false)
  })

  it('marks B_1/B_2/F_1/F_3/E_1/E_4 when routeTypes is non-empty', () => {
    const s = freshState({ routeTypes: ['3'] })
    for (const t of ['b1', 'b2', 'f1', 'f3', 'e1', 'e4']) {
      expect(isTableFiltered(s, t)).toBe(true)
    }
    expect(isTableFiltered(s, 'a1')).toBe(false)
  })

  it('marks A_1/E_1/E_4 when agIds is non-empty', () => {
    const s = freshState({ agIds: [42] })
    expect(isTableFiltered(s, 'a1')).toBe(true)
    expect(isTableFiltered(s, 'e1')).toBe(true)
    expect(isTableFiltered(s, 'e4')).toBe(true)
    expect(isTableFiltered(s, 'b1')).toBe(false)
  })

  it('marks F_1/F_3/E_1/E_4 when jourType differs from initial', () => {
    const s = freshState({ jourType: 2, initialJourType: 1 })
    for (const t of ['f1', 'f3', 'e1', 'e4']) {
      expect(isTableFiltered(s, t)).toBe(true)
    }
  })

  it('marks a table when it has a local non-mapped filter, even if no slot is set', () => {
    const s = freshState({
      tableFilters: { b2: { route_long_name: { kind: 'in', values: ['Ligne 1'] } } },
    })
    expect(isTableFiltered(s, 'b2')).toBe(true)
    expect(isTableFiltered(s, 'b1')).toBe(false)
  })
})
