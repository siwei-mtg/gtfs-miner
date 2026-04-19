import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { DashboardPage } from '@/pages/DashboardPage'
import * as apiClient from '@/api/client'

// Avoid pulling in MapLibre / recharts / AuthContext transitive deps during
// unit tests — we only care about the wiring Dashboard ↔ its children.
vi.mock('@/api/client', () => ({
  getJourTypes: vi.fn(),
}))

vi.mock('@/components/organisms/MapView', () => ({
  MapView: (props: {
    onStopClick?: (id: number, shiftKey: boolean) => void
    jourType: number
  }) => (
    <div data-testid="mock-map" data-jour-type={props.jourType}>
      <button
        data-testid="mock-map-click-ag"
        onClick={() => props.onStopClick?.(42, false)}
      >
        click AG 42
      </button>
    </div>
  ),
}))

vi.mock('@/components/PassageAGLayer', () => ({
  PassageAGLayer: () => null,
}))
vi.mock('@/components/PassageArcLayer', () => ({
  PassageArcLayer: () => null,
}))

interface MockChartsProps {
  jourType: number
  filters?: { routeTypes?: string[]; agIds?: number[] }
  onRouteTypeClick?: (rt: string) => void
}
vi.mock('@/components/organisms/DashboardCharts', () => ({
  DashboardCharts: (props: MockChartsProps) => (
    <div
      data-testid="mock-charts"
      data-jour-type={props.jourType}
      data-filters={JSON.stringify(props.filters ?? {})}
    >
      <button
        data-testid="mock-charts-click-rt"
        onClick={() => props.onRouteTypeClick?.('3')}
      >
        click Bus sector
      </button>
    </div>
  ),
}))

interface MockTableProps {
  tableName: string
  externalEnumValues?: string[]
  onFilterChange?: (f: { routeTypes?: string[] }) => void
}
vi.mock('@/components/organisms/ResultTable', () => ({
  ResultTable: (props: MockTableProps) => (
    <div
      data-testid="mock-table"
      data-table={props.tableName}
      data-external={JSON.stringify(props.externalEnumValues ?? null)}
    >
      <button
        data-testid="mock-table-filter-change"
        onClick={() => props.onFilterChange?.({ routeTypes: ['0'] })}
      >
        apply route_type=0
      </button>
    </div>
  ),
}))

// Radix Select: swap for a plain native <select> with the same aria-label.
vi.mock('@/components/ui/select', () => ({
  Select: ({ onValueChange, value, children }: any) => (
    <select
      aria-label="jour-type-select"
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: any) => <>{children}</>,
  SelectValue: () => null,
  SelectContent: ({ children }: any) => <>{children}</>,
  SelectItem: ({ value, children }: any) => <option value={value}>{children}</option>,
}))

function renderAt(pid = 'p1') {
  return render(
    <MemoryRouter initialEntries={[`/projects/${pid}/dashboard`]}>
      <Routes>
        <Route path="/projects/:id/dashboard" element={<DashboardPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.getJourTypes).mockResolvedValue([
      { value: 1, label: 'Lundi_Scolaire' },
      { value: 2, label: 'Samedi' },
    ])
  })

  it('renders map, charts, and table panels once jour-types resolve', async () => {
    renderAt()

    await waitFor(() => expect(screen.getByTestId('dashboard-page')).toBeInTheDocument())
    expect(screen.getByTestId('dashboard-map')).toBeInTheDocument()
    expect(screen.getByTestId('dashboard-charts')).toBeInTheDocument()
    expect(screen.getByTestId('dashboard-table')).toBeInTheDocument()
  })

  it('map stop click dispatches TOGGLE_AG_ID, propagating agIds to charts', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByTestId('mock-map-click-ag')).toBeInTheDocument())

    // Before click: agIds empty.
    const before = JSON.parse(screen.getByTestId('mock-charts').dataset.filters!)
    expect(before.agIds ?? []).toEqual([])

    fireEvent.click(screen.getByTestId('mock-map-click-ag'))

    await waitFor(() => {
      const after = JSON.parse(screen.getByTestId('mock-charts').dataset.filters!)
      expect(after.agIds).toEqual([42])
    })
  })

  it('chart sector click dispatches TOGGLE_ROUTE_TYPE, pushing externalEnumValues into the B1 table', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByTestId('mock-charts-click-rt')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('mock-charts-click-rt'))

    await waitFor(() => {
      const external = JSON.parse(screen.getByTestId('mock-table').dataset.external!)
      expect(external).toEqual(['3'])
    })
  })

  it('table filter change dispatches SET_ROUTE_TYPES, propagating routeTypes to charts', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByTestId('mock-table-filter-change')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('mock-table-filter-change'))

    await waitFor(() => {
      const filters = JSON.parse(screen.getByTestId('mock-charts').dataset.filters!)
      expect(filters.routeTypes).toEqual(['0'])
    })
  })

  it('jour-type select change dispatches SET_JOUR_TYPE and re-renders children with new jourType', async () => {
    renderAt()
    const select = await screen.findByLabelText('jour-type-select')
    expect(screen.getByTestId('mock-map').dataset.jourType).toBe('1')

    fireEvent.change(select, { target: { value: '2' } })

    await waitFor(() => {
      expect(screen.getByTestId('mock-map').dataset.jourType).toBe('2')
      expect(screen.getByTestId('mock-charts').dataset.jourType).toBe('2')
    })
  })
})
