import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { DashboardPage } from '@/pages/DashboardPage'
import * as apiClient from '@/api/client'

// Pull in only the endpoints Dashboard page uses at boot; the organisms
// are mocked out so we stay focused on the page wiring.
vi.mock('@/api/client', () => ({
  getJourTypes: vi.fn(),
  getKpis: vi.fn(),
  getCoursesByJourType: vi.fn(),
  getCoursesByHour: vi.fn(),
  downloadGeoPackage: vi.fn(),
  downloadProjectResults: vi.fn(),
}))

vi.mock('@/components/organisms/MapView', () => ({
  MapView: (props: { jourType: number }) => (
    <div data-testid="mock-map" data-jour-type={props.jourType} />
  ),
}))
vi.mock('@/components/PassageAGLayer', () => ({ PassageAGLayer: () => null }))
vi.mock('@/components/PassageArcLayer', () => ({ PassageArcLayer: () => null }))

vi.mock('@/components/organisms/DashboardRightPanel', () => ({
  DashboardRightPanel: () => <div data-testid="mock-right" />,
}))

vi.mock('@/components/organisms/ResultTable', () => ({
  ResultTable: (props: { tableName: string }) => (
    <div data-testid={`mock-result-table-${props.tableName}`}>{props.tableName}</div>
  ),
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

describe('DashboardPage (refonte)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.getJourTypes).mockResolvedValue([
      { value: 1, label: 'Lundi_Scolaire' },
      { value: 2, label: 'Samedi' },
    ])
    vi.mocked(apiClient.getKpis).mockResolvedValue({
      nb_lignes: 42,
      nb_arrets: 1204,
      nb_courses: 8473,
      kcc_total: 41500,
    })
  })

  it('renders the four-zone layout (sidebar rail · KPI ribbon · map · floating right panel)', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByTestId('dashboard-layout')).toBeInTheDocument())
    expect(screen.getByTestId('dashboard-sidebar')).toBeInTheDocument()
    expect(screen.getByTestId('dashboard-map')).toBeInTheDocument()
    expect(screen.getByTestId('dashboard-right')).toBeInTheDocument()
    expect(screen.getByTestId('kpi-ribbon')).toBeInTheDocument()
    // Rail mode: 6 group pastilles A–F
    expect(screen.getByTestId('sidebar-group-a')).toBeInTheDocument()
    expect(screen.getByTestId('sidebar-group-f')).toBeInTheDocument()
  })

  it('opens a group flyout then the TablePopup when a table is picked', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByTestId('dashboard-layout')).toBeInTheDocument())

    // Click group B pastille → flyout opens with B_1, B_2
    fireEvent.click(screen.getByTestId('sidebar-group-b'))
    await waitFor(() =>
      expect(screen.getByTestId('sidebar-table-b1')).toBeInTheDocument(),
    )

    // Click B_1 → popup opens, flyout closes
    fireEvent.click(screen.getByTestId('sidebar-table-b1'))
    await waitFor(() =>
      expect(screen.getByTestId('mock-result-table-b1')).toBeInTheDocument(),
    )
  })

  it('reset-filters button is disabled when no filter is active', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByTestId('dashboard-layout')).toBeInTheDocument())
    const reset = screen.getByLabelText('reset-filters')
    expect(reset).toBeDisabled()
  })
})
