import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UploadForm } from '../components/UploadForm'

const gtfsFile = new File(['zip-content'], 'gtfs.zip', { type: 'application/zip' })

describe('UploadForm', () => {
  it('renders file input and submit button', () => {
    render(<UploadForm onSubmit={vi.fn()} />)
    expect(screen.getByLabelText('GTFS ZIP')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /lancer/i })).toBeInTheDocument()
  })

  it('submit button is disabled when no file is selected', () => {
    render(<UploadForm onSubmit={vi.fn()} />)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('submit button is disabled when isLoading is true', async () => {
    const user = userEvent.setup()
    render(<UploadForm onSubmit={vi.fn()} isLoading />)
    await user.upload(screen.getByLabelText('GTFS ZIP'), gtfsFile)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('submit button is enabled after file is selected', async () => {
    const user = userEvent.setup()
    render(<UploadForm onSubmit={vi.fn()} />)
    await user.upload(screen.getByLabelText('GTFS ZIP'), gtfsFile)
    expect(screen.getByRole('button')).toBeEnabled()
  })

  it('calls onSubmit with file and default params on submit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<UploadForm onSubmit={onSubmit} />)

    await user.upload(screen.getByLabelText('GTFS ZIP'), gtfsFile)
    await user.click(screen.getByRole('button'))

    expect(onSubmit).toHaveBeenCalledOnce()
    const [calledFile, calledParams] = onSubmit.mock.calls[0]
    expect(calledFile.name).toBe('gtfs.zip')
    expect(calledParams.hpm_debut).toBe('07:00')
    expect(calledParams.vacances).toBe('A')
  })

  it('shows loading label when isLoading is true', () => {
    render(<UploadForm onSubmit={vi.fn()} isLoading />)
    expect(screen.getByRole('button')).toHaveTextContent(/traitement en cours/i)
  })

  it('displays error message when error prop is set', () => {
    render(<UploadForm onSubmit={vi.fn()} error="Upload failed" />)
    expect(screen.getByRole('alert')).toHaveTextContent('Upload failed')
  })

  it('does not call onSubmit when form submitted without file', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<UploadForm onSubmit={onSubmit} />)
    // Button is disabled, so click should not fire submit
    await user.click(screen.getByRole('button'))
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
