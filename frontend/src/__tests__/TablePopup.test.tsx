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

  it('debounces resolveTableFilters and dispatches the resolved canonical IDs', async () => {
    vi.mocked(apiClient.resolveTableFilters).mockResolvedValue({
      ligne_ids: [42, 43],
      route_types: ['3'],
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

    // Reducer should reflect the resolved IDs.
    await waitFor(() => {
      const state = probe.mock.calls.at(-1)?.[0].state
      expect(state.ligneIds).toEqual([42, 43])
      expect(state.routeTypes).toEqual(['3'])
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

