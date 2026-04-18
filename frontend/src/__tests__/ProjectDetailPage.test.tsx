import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import userEvent from '@testing-library/user-event'

const useProjectProgressMock = vi.fn(() => ({
  messages: [],
  latestStatus: 'processing' as 'processing' | 'completed',
  isConnected: true,
}))

vi.mock('@/hooks/useProjectProgress', () => ({
  useProjectProgress: () => useProjectProgressMock(),
}))

vi.mock('@/components/organisms/MapView', () => ({
  MapView: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="map-view">{children}</div>
  ),
}))
vi.mock('@/components/PassageAGLayer', () => ({ PassageAGLayer: () => null }))
vi.mock('@/components/PassageArcLayer', () => ({ PassageArcLayer: () => null }))

const downloadGeoPackageMock = vi.fn().mockResolvedValue(undefined)
const getJourTypesMock = vi.fn().mockResolvedValue([{ value: 1, label: 'Lun-Ven' }])

vi.mock('@/api/client', async (orig) => {
  const actual = await orig<typeof import('@/api/client')>()
  return {
    ...actual,
    getJourTypes: (...args: Parameters<typeof actual.getJourTypes>) =>
      getJourTypesMock(...args),
    downloadGeoPackage: (...args: Parameters<typeof actual.downloadGeoPackage>) =>
      downloadGeoPackageMock(...args),
  }
})

function renderPage(projectId = 'p123') {
  return render(
    <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
      <Routes>
        <Route path="/" element={<div>Project List Page</div>} />
        <Route path="/projects/:id" element={<ProjectDetailPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProjectDetailPage', () => {
  beforeEach(() => {
    useProjectProgressMock.mockReset()
    useProjectProgressMock.mockReturnValue({
      messages: [],
      latestStatus: 'processing',
      isConnected: true,
    })
    downloadGeoPackageMock.mockClear()
    getJourTypesMock.mockClear()
    getJourTypesMock.mockResolvedValue([{ value: 1, label: 'Lun-Ven' }])
  })

  it('test_project_detail_back_button', async () => {
    const user = userEvent.setup()
    renderPage()

    const backButton = screen.getByLabelText('back-button')
    expect(backButton).toBeInTheDocument()

    await user.click(backButton)
    expect(screen.getByText('Project List Page')).toBeInTheDocument()
  })

  it('test_gpkg_button_exists', async () => {
    useProjectProgressMock.mockReturnValue({
      messages: [],
      latestStatus: 'completed',
      isConnected: true,
    })
    const user = userEvent.setup()
    renderPage()

    await user.click(screen.getByRole('button', { name: /carte/i }))

    const button = await screen.findByLabelText('download-geopackage-button')
    expect(button).toBeInTheDocument()
  })

  it('test_gpkg_button_triggers_download', async () => {
    useProjectProgressMock.mockReturnValue({
      messages: [],
      latestStatus: 'completed',
      isConnected: true,
    })
    const user = userEvent.setup()
    renderPage('p123')

    await user.click(screen.getByRole('button', { name: /carte/i }))

    const button = await screen.findByLabelText('download-geopackage-button')
    await user.click(button)

    expect(downloadGeoPackageMock).toHaveBeenCalledWith('p123', 1)
  })
})
