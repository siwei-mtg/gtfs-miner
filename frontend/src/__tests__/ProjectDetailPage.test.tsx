import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ProjectDetailPage } from '@/pages/ProjectDetailPage'
import userEvent from '@testing-library/user-event'

vi.mock('@/hooks/useProjectProgress', () => ({
  useProjectProgress: () => ({
    messages: [],
    latestStatus: 'processing',
    isConnected: true,
  }),
}))

describe('ProjectDetailPage', () => {
  it('test_project_detail_back_button', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/projects/p123']}>
        <Routes>
          <Route path="/" element={<div>Project List Page</div>} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    )

    const backButton = screen.getByLabelText('back-button')
    expect(backButton).toBeInTheDocument()

    await user.click(backButton)
    expect(screen.getByText('Project List Page')).toBeInTheDocument()
  })
})
