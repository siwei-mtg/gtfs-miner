import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { TablePopup } from '@/components/organisms/TablePopup'
import { DashboardSyncProvider, useDashboardSync } from '@/hooks/useDashboardSync'
import * as apiClient from '../api/client'

// ── Stubs ──────────────────────────────────────────────────────────────────
// We only care about TablePopup wiring (state.tableFilters mirroring +
// SET_TABLE_FILTERS dispatch + scheduleResolve).  Mock ResultTable so we can
// trigger its callbacks directly without exercising the whole filter UI.

const mockResultTableProps = vi.fn()

vi.mock('@/components/organisms/ResultTable', () => ({
  ResultTable: (props: any) => {
    mockResultTableProps(props)
    return <div data-testid="mock-result-table">{props.tableName}</div>
  },
}))

vi.mock('../api/client', () => ({
  resolveTableFilters: vi.fn(),
}))

// Radix Dialog uses portals; jsdom is fine but we still want a clean root.
function renderWithProvider(ui: React.ReactElement) {
  return render(
    <DashboardSyncProvider initialJourType={1}>{ui}</DashboardSyncProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(apiClient.resolveTableFilters).mockResolvedValue({
    ligne_ids: [],
    route_types: [],
    ag_ids: [],
  })
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
})

// Tiny helper: pull the latest ResultTable prop bag so we can call its
// onAllColumnFiltersChange / onFilterChange directly.
function latestProps() {
  return mockResultTableProps.mock.calls.at(-1)?.[0]
}

describe('TablePopup', () => {
  it('externalColumnFilters mirror state.tableFilters[tableId] only', async () => {
    // Probe that lets us seed the context after mount.
    const probe = vi.fn<(s: any) => void>()
    function Probe() {
      const { state, dispatch } = useDashboardSync()
      probe({ state, dispatch })
      return null
    }

    renderWithProvider(
      <>
        <Probe />
        <TablePopup projectId="p1" tableId="b2" onClose={() => {}} />
      </>,
    )
    await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

    // Initially empty.
    expect(latestProps().externalColumnFilters).toEqual({})

    // Seed a per-table filter via the reducer.
    const dispatch = probe.mock.calls.at(-1)?.[0].dispatch
    act(() => {
      dispatch({
        type: 'SET_TABLE_FILTERS',
        tableId: 'b2',
        payload: { route_long_name: { kind: 'in', values: ['Ligne 1'] } },
      })
    })

    await waitFor(() => {
      expect(latestProps().externalColumnFilters).toEqual({
        route_long_name: { kind: 'in', values: ['Ligne 1'] },
      })
    })
  })

  it('does NOT mirror state.routeTypes / state.ligneIds back into the table view', async () => {
    // Old behaviour: a chart-set routeTypes=['3'] would show up as a
    // route_type chip in the b1 table.  We deliberately removed that to
    // avoid the resolve-loop UX issue.
    const probe = vi.fn<(s: any) => void>()
    function Probe() {
      const { dispatch } = useDashboardSync()
      probe({ dispatch })
      return null
    }
    renderWithProvider(
      <>
        <Probe />
        <TablePopup projectId="p1" tableId="b1" onClose={() => {}} />
      </>,
    )
    await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

    const dispatch = probe.mock.calls.at(-1)?.[0].dispatch
    act(() => {
      dispatch({ type: 'SET_ROUTE_TYPES', payload: ['3'] })
    })

    // Still empty — mapped slots no longer mirror.
    await waitFor(() => expect(latestProps().externalColumnFilters).toEqual({}))
  })

  it('onAllColumnFiltersChange dispatches SET_TABLE_FILTERS', async () => {
    const probe = vi.fn<(s: any) => void>()
    function Probe() {
      const ctx = useDashboardSync()
      probe(ctx)
      return null
    }
    renderWithProvider(
      <>
        <Probe />
        <TablePopup projectId="p1" tableId="b2" onClose={() => {}} />
      </>,
    )
    await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

    act(() => {
      latestProps().onAllColumnFiltersChange({
        route_long_name: { kind: 'in', values: ['Ligne 1'] },
      })
    })

    await waitFor(() => {
      const state = probe.mock.calls.at(-1)?.[0].state
      expect(state.tableFilters.b2).toEqual({
        route_long_name: { kind: 'in', values: ['Ligne 1'] },
      })
    })
  })

  it('debounces resolveTableFilters and dispatches APPLY_RESOLVED with source', async () => {
    vi.mocked(apiClient.resolveTableFilters).mockResolvedValue({
      ligne_ids: [42, 43],
      route_types: ['3'],
      ag_ids: [100, 200],
    })
    const probe = vi.fn<(s: any) => void>()
    function Probe() {
      const ctx = useDashboardSync()
      probe(ctx)
      return null
    }
    renderWithProvider(
      <>
        <Probe />
        <TablePopup projectId="p1" tableId="b2" onClose={() => {}} />
      </>,
    )
    await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

    act(() => {
      latestProps().onAllColumnFiltersChange({
        route_long_name: { kind: 'in', values: ['Ligne 1'] },
      })
    })

    // Before debounce window, no call.
    expect(apiClient.resolveTableFilters).not.toHaveBeenCalled()

    // Advance past debounce.
    await act(async () => {
      vi.advanceTimersByTime(300)
      await Promise.resolve()
    })

    expect(apiClient.resolveTableFilters).toHaveBeenCalledWith(
      'p1',
      'b2',
      { route_long_name: { kind: 'in', values: ['Ligne 1'] } },
    )

    // Reducer should reflect the resolved IDs AND the source tableId so the
    // banner / context-filter logic can suppress redundancy on the source.
    await waitFor(() => {
      const state = probe.mock.calls.at(-1)?.[0].state
      expect(state.ligneIds).toEqual([42, 43])
      expect(state.routeTypes).toEqual(['3'])
      expect(state.resolveSource).toBe('b2')
    })
  })

  describe('contextFilters wiring', () => {
    it('passes context filters to ResultTable when target table has the column and is NOT the source', async () => {
      const probe = vi.fn<(s: any) => void>()
      function Probe() {
        const ctx = useDashboardSync()
        probe(ctx)
        return null
      }
      renderWithProvider(
        <>
          <Probe />
          <TablePopup projectId="p1" tableId="f1" onClose={() => {}} />
        </>,
      )
      await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

      // Simulate a previous resolve from a DIFFERENT table (b2) populating
      // the canonical slot.
      const dispatch = probe.mock.calls.at(-1)?.[0].dispatch
      act(() => {
        dispatch({
          type: 'APPLY_RESOLVED',
          payload: { ligneIds: [1, 2], routeTypes: [], agIds: [], source: 'b2' },
        })
      })

      // F_1 has id_ligne_num so the context propagates.
      await waitFor(() => {
        expect(latestProps().contextFilters).toEqual({
          id_ligne_num: { kind: 'in', values: ['1', '2'] },
        })
      })
    })

    it('does NOT pass context filters when the target table IS the resolve source', async () => {
      const probe = vi.fn<(s: any) => void>()
      function Probe() {
        const ctx = useDashboardSync()
        probe(ctx)
        return null
      }
      renderWithProvider(
        <>
          <Probe />
          <TablePopup projectId="p1" tableId="b2" onClose={() => {}} />
        </>,
      )
      await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

      const dispatch = probe.mock.calls.at(-1)?.[0].dispatch
      act(() => {
        dispatch({
          type: 'APPLY_RESOLVED',
          payload: { ligneIds: [1, 2], routeTypes: [], agIds: [], source: 'b2' },
        })
      })

      // B_2 IS the source — its tableFilters local is strictly more
      // restrictive, so contextFilters must stay empty to avoid noise.
      await waitFor(() => {
        expect(latestProps().contextFilters).toEqual({})
      })
    })

    it('does NOT pass context for canonical columns the target table lacks', async () => {
      const probe = vi.fn<(s: any) => void>()
      function Probe() {
        const ctx = useDashboardSync()
        probe(ctx)
        return null
      }
      renderWithProvider(
        <>
          <Probe />
          <TablePopup projectId="p1" tableId="e1" onClose={() => {}} />
        </>,
      )
      await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

      const dispatch = probe.mock.calls.at(-1)?.[0].dispatch
      act(() => {
        dispatch({
          type: 'APPLY_RESOLVED',
          payload: { ligneIds: [1], routeTypes: ['3'], agIds: [], source: 'b2' },
        })
      })

      // E_1 doesn't carry id_ligne_num or route_type, so context stays empty.
      await waitFor(() => {
        expect(latestProps().contextFilters).toEqual({})
      })
    })

    it('lets a local filter on a canonical column take precedence over context', async () => {
      const probe = vi.fn<(s: any) => void>()
      function Probe() {
        const ctx = useDashboardSync()
        probe(ctx)
        return null
      }
      renderWithProvider(
        <>
          <Probe />
          <TablePopup projectId="p1" tableId="f1" onClose={() => {}} />
        </>,
      )
      await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

      const dispatch = probe.mock.calls.at(-1)?.[0].dispatch
      act(() => {
        dispatch({
          type: 'APPLY_RESOLVED',
          payload: { ligneIds: [1, 2], routeTypes: [], agIds: [], source: 'b2' },
        })
        dispatch({
          type: 'SET_TABLE_FILTERS',
          tableId: 'f1',
          payload: { id_ligne_num: { kind: 'in', values: ['9'] } },
        })
      })

      // The local F_1 filter on id_ligne_num must NOT be shadowed by the
      // context-derived id_ligne_num — context omits the column entirely.
      await waitFor(() => {
        expect(latestProps().contextFilters).toEqual({})
        expect(latestProps().externalColumnFilters).toEqual({
          id_ligne_num: { kind: 'in', values: ['9'] },
        })
      })
    })

    it('renders the context banner when context filters are present', async () => {
      const probe = vi.fn<(s: any) => void>()
      function Probe() {
        const ctx = useDashboardSync()
        probe(ctx)
        return null
      }
      renderWithProvider(
        <>
          <Probe />
          <TablePopup projectId="p1" tableId="f1" onClose={() => {}} />
        </>,
      )
      await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

      // No banner before context exists.
      expect(screen.queryByTestId('context-filter-banner')).toBeNull()

      const dispatch = probe.mock.calls.at(-1)?.[0].dispatch
      act(() => {
        dispatch({
          type: 'APPLY_RESOLVED',
          payload: { ligneIds: [1], routeTypes: [], agIds: [], source: 'b2' },
        })
      })

      await waitFor(() => {
        expect(screen.getByTestId('context-filter-banner')).toBeInTheDocument()
      })
      expect(screen.getByTestId('context-filter-banner').textContent).toContain('1 ligne')
    })
  })

  it('does NOT call resolveTableFilters when filters become empty (preserves chart state)', async () => {
    const probe = vi.fn<(s: any) => void>()
    function Probe() {
      const ctx = useDashboardSync()
      probe(ctx)
      return null
    }
    renderWithProvider(
      <>
        <Probe />
        <TablePopup projectId="p1" tableId="b2" onClose={() => {}} />
      </>,
    )
    await waitFor(() => expect(screen.getByTestId('mock-result-table')).toBeInTheDocument())

    // Seed a chart-driven routeTypes via direct dispatch.
    const dispatch = probe.mock.calls.at(-1)?.[0].dispatch
    act(() => {
      dispatch({ type: 'SET_ROUTE_TYPES', payload: ['3'] })
    })

    // User clears all table filters.
    act(() => {
      latestProps().onAllColumnFiltersChange({})
    })

    await act(async () => {
      vi.advanceTimersByTime(500)
      await Promise.resolve()
    })

    expect(apiClient.resolveTableFilters).not.toHaveBeenCalled()

    // Chart-driven routeTypes must still be intact.
    const state = probe.mock.calls.at(-1)?.[0].state
    expect(state.routeTypes).toEqual(['3'])
  })
})

