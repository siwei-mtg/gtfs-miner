import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'
import * as client from '../api/client'
import * as useProjectProgressModule from '../hooks/useProjectProgress'
import type { WebSocketMessage } from '../types/api'

const mockProject = {
  id: 'proj-test',
  status: 'pending' as const,
  created_at: '2026-04-07T00:00:00',
  updated_at: '2026-04-07T00:00:00',
  parameters: {
    hpm_debut: '07:00', hpm_fin: '09:00',
    hps_debut: '17:00', hps_fin: '19:30',
    vacances: 'A', pays: '法国',
  },
  error_message: null,
}

function makeMsg(step: string, status: WebSocketMessage['status'] = 'processing'): WebSocketMessage {
  return { project_id: 'proj-test', status, step, time_elapsed: 1.0, error: null }
}

beforeEach(() => {
  vi.restoreAllMocks()
  // Default: hook returns no messages
  vi.spyOn(useProjectProgressModule, 'useProjectProgress').mockReturnValue({
    messages: [],
    latestStatus: null,
    isConnected: false,
  })
})

describe('App', () => {
  it('shows UploadForm in initial idle state', () => {
    render(<App />)
    expect(screen.getByLabelText('GTFS ZIP')).toBeInTheDocument()
    expect(screen.queryByLabelText('progress-panel')).not.toBeInTheDocument()
  })

  it('switches to ProgressPanel view after successful upload', async () => {
    vi.spyOn(client, 'createProject').mockResolvedValue(mockProject)
    vi.spyOn(client, 'uploadGtfs').mockResolvedValue({ msg: 'ok', project_id: 'proj-test' })

    const user = userEvent.setup()
    render(<App />)

    await user.upload(
      screen.getByLabelText('GTFS ZIP'),
      new File(['zip'], 'gtfs.zip', { type: 'application/zip' })
    )
    await user.click(screen.getByRole('button', { name: /lancer/i }))

    await waitFor(() =>
      expect(screen.getByLabelText('progress-panel')).toBeInTheDocument()
    )
    expect(screen.queryByLabelText('GTFS ZIP')).not.toBeInTheDocument()
  })

  it('shows disabled download button while processing', async () => {
    vi.spyOn(client, 'createProject').mockResolvedValue(mockProject)
    vi.spyOn(client, 'uploadGtfs').mockResolvedValue({ msg: 'ok', project_id: 'proj-test' })
    vi.spyOn(useProjectProgressModule, 'useProjectProgress').mockReturnValue({
      messages: [makeMsg('[1/7] 读取与解压 GTFS 文件')],
      latestStatus: 'processing',
      isConnected: true,
    })

    const user = userEvent.setup()
    render(<App />)

    await user.upload(
      screen.getByLabelText('GTFS ZIP'),
      new File(['zip'], 'gtfs.zip', { type: 'application/zip' })
    )
    await user.click(screen.getByRole('button', { name: /lancer/i }))

    await waitFor(() =>
      expect(screen.getByLabelText('progress-panel')).toBeInTheDocument()
    )
    expect(screen.getByLabelText('download-button')).toBeDisabled()
  })

  it('enables download button when processing is completed', async () => {
    vi.spyOn(client, 'createProject').mockResolvedValue(mockProject)
    vi.spyOn(client, 'uploadGtfs').mockResolvedValue({ msg: 'ok', project_id: 'proj-test' })
    vi.spyOn(useProjectProgressModule, 'useProjectProgress').mockReturnValue({
      messages: [makeMsg('处理完成', 'completed')],
      latestStatus: 'completed',
      isConnected: false,
    })

    const user = userEvent.setup()
    render(<App />)

    await user.upload(
      screen.getByLabelText('GTFS ZIP'),
      new File(['zip'], 'gtfs.zip', { type: 'application/zip' })
    )
    await user.click(screen.getByRole('button', { name: /lancer/i }))

    await waitFor(() =>
      expect(screen.getByLabelText('download-button')).not.toBeDisabled()
    )
    expect(screen.getByLabelText('download-button')).toHaveAttribute(
      'href',
      '/api/v1/projects/proj-test/download'
    )
  })

  it('shows upload error and returns to idle on API failure', async () => {
    vi.spyOn(client, 'createProject').mockRejectedValue(new Error('Network error'))

    const user = userEvent.setup()
    render(<App />)

    await user.upload(
      screen.getByLabelText('GTFS ZIP'),
      new File(['zip'], 'gtfs.zip', { type: 'application/zip' })
    )
    await user.click(screen.getByRole('button', { name: /lancer/i }))

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Network error')
    )
    expect(screen.getByLabelText('GTFS ZIP')).toBeInTheDocument()
  })
})
