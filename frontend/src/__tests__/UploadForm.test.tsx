import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UploadForm } from '../components/UploadForm'

const gtfsFile = new File(['zip-content'], 'gtfs.zip', { type: 'application/zip' })

describe('UploadForm / ParametersForm', () => {
  it('test_renders_all_fields', () => {
    render(<UploadForm onSubmit={vi.fn()} />)
    expect(screen.getByLabelText('GTFS ZIP')).toBeInTheDocument()
    expect(screen.getByLabelText(/HP matin début/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/HP matin fin/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/HP soir début/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/HP soir fin/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Vacances/i)).toBeInTheDocument()
  })

  it('test_default_values', () => {
    render(<UploadForm onSubmit={vi.fn()} />)
    expect(screen.getByLabelText(/HP matin début/i)).toHaveValue('07:00')
    expect(screen.getByLabelText(/HP matin fin/i)).toHaveValue('09:00')
    expect(screen.getByLabelText(/HP soir début/i)).toHaveValue('17:00')
    expect(screen.getByLabelText(/HP soir fin/i)).toHaveValue('19:30')
    expect(screen.getByLabelText(/Vacances/i)).toHaveValue('A')
    const hiddenPays = document.getElementById('pays') as HTMLInputElement
    expect(hiddenPays).toHaveValue('france')
  })

  it('test_vacances_options', () => {
    render(<UploadForm onSubmit={vi.fn()} />)
    const select = screen.getByLabelText(/Vacances/i) as HTMLSelectElement
    const options = Array.from(select.options).map(opt => opt.value)
    expect(options).toEqual(['A', 'B', 'C', '全部'])
  })

  it('test_submit_with_params', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<UploadForm onSubmit={onSubmit} />)

    await user.upload(screen.getByLabelText('GTFS ZIP'), gtfsFile)
    const select = screen.getByLabelText(/Vacances/i)
    await user.selectOptions(select, 'B')
    
    await user.click(screen.getByRole('button', { name: /lancer/i }))

    expect(onSubmit).toHaveBeenCalledOnce()
    const [calledFile, calledParams] = onSubmit.mock.calls[0]
    expect(calledFile.name).toBe('gtfs.zip')
    expect(calledParams.vacances).toBe('B')
    expect(calledParams.pays).toBe('france')
  })

  it('test_disabled_while_loading', async () => {
    const user = userEvent.setup()
    render(<UploadForm onSubmit={vi.fn()} isLoading />)
    await user.upload(screen.getByLabelText('GTFS ZIP'), gtfsFile)
    expect(screen.getByRole('button')).toBeDisabled()
    expect(screen.getByRole('button')).toHaveTextContent(/traitement en cours/i)
  })

  it('test_time_field_validation', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<UploadForm onSubmit={onSubmit} />)

    await user.upload(screen.getByLabelText('GTFS ZIP'), gtfsFile)
    
    // Set invalid time range hpm_fin <= hpm_debut
    const debutInput = screen.getByLabelText(/HP matin début/i)
    const finInput = screen.getByLabelText(/HP matin fin/i)
    
    await user.clear(debutInput)
    await user.type(debutInput, '10:00')
    await user.clear(finInput)
    await user.type(finInput, '09:00')
    
    await user.click(screen.getByRole('button', { name: /lancer/i }))
    
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent(/postérieure au début/i)

    // Fix it
    await user.clear(finInput)
    await user.type(finInput, '11:00')
    await user.click(screen.getByRole('button', { name: /lancer/i }))
    
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(onSubmit).toHaveBeenCalledOnce()
  })
})
