import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { DashboardCharts } from '@/components/organisms/DashboardCharts'
import { getPeakOffpeak, getTableData } from '@/api/client'

vi.mock('@/api/client', () => ({
  getTableData: vi.fn(),
  getPeakOffpeak: vi.fn(),
}))

/**
 * Recharts' ResponsiveContainer uses ResizeObserver, which jsdom does not
 * provide; polyfilling it silences recharts' console noise without affecting
 * the tests (which assert on Card-level test IDs, not SVG shapes).
 */
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
;(globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver =
  ResizeObserverStub

const mockedGetTableData = vi.mocked(getTableData)
const mockedGetPeakOffpeak = vi.mocked(getPeakOffpeak)

function buildB1Rows() {
  return [
    { id_ligne_num: 1, route_short_name: 'L1', route_type: 3 },
    { id_ligne_num: 2, route_short_name: 'L2', route_type: 3 },
    { id_ligne_num: 3, route_short_name: 'L3', route_type: 0 },
  ]
}
function buildF1Rows() {
  return [
    { id_ligne_num: 1, route_short_name: 'L1', type_jour: 1, nb_course: 120 },
    { id_ligne_num: 2, route_short_name: 'L2', type_jour: 1, nb_course: 80 },
    { id_ligne_num: 1, route_short_name: 'L1', type_jour: 2, nb_course: 300 }, // filtered out
  ]
}
function buildF3Rows() {
  return [
    { id_ligne_num: 1, route_short_name: 'L1', type_jour: 1, kcc: 45.2 },
    { id_ligne_num: 2, route_short_name: 'L2', type_jour: 1, kcc: 12.9 },
  ]
}
function buildPeakRows() {
  return [
    { id_ag_num: 10, stop_name: 'Alpha', peak_count: 20, offpeak_count: 30 },
    { id_ag_num: 20, stop_name: 'Beta', peak_count: 5, offpeak_count: 2 },
  ]
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedGetTableData.mockImplementation(async (_pid, tableName) => {
    if (tableName === 'b1_lignes') {
      return { total: 3, rows: buildB1Rows(), columns: ['id_ligne_num', 'route_type'] }
    }
    if (tableName === 'f1_nb_courses_lignes') {
      return { total: 3, rows: buildF1Rows(), columns: ['id_ligne_num', 'type_jour', 'nb_course'] }
    }
    if (tableName === 'f3_kcc_lignes') {
      return { total: 2, rows: buildF3Rows(), columns: ['id_ligne_num', 'type_jour', 'kcc'] }
    }
    return { total: 0, rows: [], columns: [] }
  })
  mockedGetPeakOffpeak.mockResolvedValue({ rows: buildPeakRows() })
})

describe('DashboardCharts', () => {
  it('renders four chart cards', async () => {
    render(<DashboardCharts projectId="p1" jourType={1} />)

    await waitFor(() => {
      expect(screen.getByTestId('chart-route-type')).toBeInTheDocument()
      expect(screen.getByTestId('chart-top-courses')).toBeInTheDocument()
      expect(screen.getByTestId('chart-top-kcc')).toBeInTheDocument()
      expect(screen.getByTestId('chart-peak-offpeak')).toBeInTheDocument()
    })
  })

  it('fetches B_1 / F_1 / F_3 tables and peak-offpeak on mount', async () => {
    render(<DashboardCharts projectId="p1" jourType={1} />)

    await waitFor(() => expect(mockedGetTableData).toHaveBeenCalledTimes(3))
    const calledTables = mockedGetTableData.mock.calls.map((c) => c[1])
    expect(calledTables).toContain('b1_lignes')
    expect(calledTables).toContain('f1_nb_courses_lignes')
    expect(calledTables).toContain('f3_kcc_lignes')

    expect(mockedGetPeakOffpeak).toHaveBeenCalledWith('p1', 1)
  })

  it('refetches when filters prop changes', async () => {
    const { rerender } = render(
      <DashboardCharts projectId="p1" jourType={1} filters={{}} />,
    )
    await waitFor(() => expect(mockedGetTableData).toHaveBeenCalledTimes(3))
    await waitFor(() => expect(mockedGetPeakOffpeak).toHaveBeenCalledTimes(1))

    rerender(
      <DashboardCharts projectId="p1" jourType={1} filters={{ routeTypes: ['3'] }} />,
    )
    await waitFor(() => expect(mockedGetTableData).toHaveBeenCalledTimes(6))
    await waitFor(() => expect(mockedGetPeakOffpeak).toHaveBeenCalledTimes(2))
  })

  it('sorts F_1 request with nb_course desc and caps limit at 200', async () => {
    render(<DashboardCharts projectId="p1" jourType={1} />)
    await waitFor(() => expect(mockedGetTableData).toHaveBeenCalled())
    const f1Call = mockedGetTableData.mock.calls.find((c) => c[1] === 'f1_nb_courses_lignes')
    expect(f1Call).toBeDefined()
    expect(f1Call![2]).toMatchObject({
      sort_by: 'nb_course',
      sort_order: 'desc',
      limit: 200,
    })
  })
})
