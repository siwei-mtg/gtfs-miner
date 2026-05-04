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
    resolveSource: null,
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
      resolveSource: 'b2',
    })
    const next = dashboardSyncReducer(s, { type: 'CLEAR_FILTERS' })
    expect(next.jourType).toBe(1)
    expect(next.routeTypes).toEqual([])
    expect(next.ligneIds).toEqual([])
    expect(next.agIds).toEqual([])
    expect(next.hoursSelected).toEqual([])
    expect(next.tableFilters).toEqual({})
    expect(next.resolveSource).toBeNull()
  })
})

describe('dashboardSyncReducer — APPLY_RESOLVED', () => {
  it('atomically writes ligneIds, routeTypes, and resolveSource', () => {
    const next = dashboardSyncReducer(freshState(), {
      type: 'APPLY_RESOLVED',
      payload: { ligneIds: [1, 2], routeTypes: ['3'], agIds: [], source: 'b2' },
    })
    expect(next.ligneIds).toEqual([1, 2])
    expect(next.routeTypes).toEqual(['3'])
    expect(next.resolveSource).toBe('b2')
  })

  it('returns the same state when payload matches existing slots and source', () => {
    const s = freshState({ ligneIds: [1, 2], routeTypes: ['3'], resolveSource: 'b2' })
    const next = dashboardSyncReducer(s, {
      type: 'APPLY_RESOLVED',
      payload: { ligneIds: [1, 2], routeTypes: ['3'], agIds: [], source: 'b2' },
    })
    expect(next).toBe(s)
  })

  it('updates resolveSource even when slots are unchanged but the source differs', () => {
    const s = freshState({ ligneIds: [1, 2], routeTypes: ['3'], resolveSource: 'b2' })
    const next = dashboardSyncReducer(s, {
      type: 'APPLY_RESOLVED',
      payload: { ligneIds: [1, 2], routeTypes: ['3'], agIds: [], source: 'f1' },
    })
    expect(next.resolveSource).toBe('f1')
  })
})

describe('dashboardSyncReducer — resolveSource invalidation', () => {
  it('SET_LIGNE_IDS clears resolveSource', () => {
    const s = freshState({ ligneIds: [1], resolveSource: 'b2' })
    const next = dashboardSyncReducer(s, { type: 'SET_LIGNE_IDS', payload: [9] })
    expect(next.ligneIds).toEqual([9])
    expect(next.resolveSource).toBeNull()
  })

  it('SET_ROUTE_TYPES clears resolveSource', () => {
    const s = freshState({ routeTypes: ['3'], resolveSource: 'b2' })
    const next = dashboardSyncReducer(s, { type: 'SET_ROUTE_TYPES', payload: ['0'] })
    expect(next.routeTypes).toEqual(['0'])
    expect(next.resolveSource).toBeNull()
  })

  it('TOGGLE_ROUTE_TYPE clears resolveSource', () => {
    const s = freshState({ routeTypes: ['3'], resolveSource: 'b2' })
    const next = dashboardSyncReducer(s, { type: 'TOGGLE_ROUTE_TYPE', payload: '0' })
    expect(next.routeTypes).toEqual(['3', '0'])
    expect(next.resolveSource).toBeNull()
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

  it('marks only tables that have route_type when routeTypes is non-empty', () => {
    // B_1 carries route_type; B_2/F_1/F_3 don't (only id_ligne_num).  E_1/E_4
    // have neither, so they must NOT light up — that was the "lying mark" bug.
    const s = freshState({ routeTypes: ['3'] })
    expect(isTableFiltered(s, 'b1')).toBe(true)
    for (const t of ['b2', 'f1', 'f3', 'e1', 'e4', 'a1']) {
      expect(isTableFiltered(s, t)).toBe(false)
    }
  })

  it('marks only tables that have id_ligne_num when ligneIds is non-empty', () => {
    // E_1/E_4 are indexed by id_ag_num, NOT id_ligne_num — they must stay
    // unmarked when only the line filter is set (we can't filter their data
    // by line without a cross-table JOIN, out of scope).
    const s = freshState({ ligneIds: [1, 2] })
    for (const t of ['b1', 'b2', 'f1', 'f3']) {
      expect(isTableFiltered(s, t)).toBe(true)
    }
    for (const t of ['e1', 'e4', 'a1']) {
      expect(isTableFiltered(s, t)).toBe(false)
    }
  })

  it('marks A_1/E_1 (id_ag_num) when agIds is non-empty, NOT E_4', () => {
    // E_4 has id_ag_num_a / id_ag_num_b (not id_ag_num) — current TABLE_COLUMNS
    // carries an empty set for E_4 so it doesn't light up.  See plan §"Hors
    // scope" for the open question on which side (a/b) to filter.
    const s = freshState({ agIds: [42] })
    expect(isTableFiltered(s, 'a1')).toBe(true)
    expect(isTableFiltered(s, 'e1')).toBe(true)
    expect(isTableFiltered(s, 'e4')).toBe(false)
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
