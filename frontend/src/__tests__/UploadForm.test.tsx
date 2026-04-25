import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UploadForm } from '@/components/organisms/UploadForm'

const gtfsFile = new File(['zip-content'], 'gtfs.zip', { type: 'application/zip' })

describe('UploadForm / ParametersForm', () => {
  it('test_renders_all_fields', () => {
    render(<UploadForm onSubmit={vi.fn()} />)
    expect(screen.getByLabelText('GTFS ZIP')).toBeInTheDocument()
    expect(screen.getByLabelText(/HP matin début/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/HP matin fin/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/HP soir début/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/HP soir fin/i)).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /Vacances/i })).toBeInTheDocument()
  })

  it('test_default_values', () => {
    render(<UploadForm onSubmit={vi.fn()} />)
    expect(screen.getByLabelText(/HP matin début/i)).toHaveValue('07:00')
    expect(screen.getByLabelText(/HP matin fin/i)).toHaveValue('09:00')
    expect(screen.getByLabelText(/HP soir début/i)).toHaveValue('17:00')
    expect(screen.getByLabelText(/HP soir fin/i)).toHaveValue('19:30')
    
    const hiddenPays = document.getElementById('pays') as HTMLInputElement
    expect(hiddenPays).toHaveValue('france')
  })

  it('test_vacances_options', () => {
    render(<UploadForm onSubmit={vi.fn()} />)
    const hiddenSelect = document.querySelector('select[name="vacances"]') as HTMLSelectElement
    const options = Array.from(hiddenSelect.options).map(opt => opt.value)
    expect(options).toEqual(['A', 'B', 'C', '全部'])
  })

  it('test_submit_with_params', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<UploadForm onSubmit={onSubmit} />)

    const fileInput = screen.getByLabelText('GTFS ZIP')
    await user.upload(fileInput, gtfsFile)
    
    const hiddenSelect = document.querySelector('select[name="vacances"]') as HTMLSelectElement
    fireEvent.change(hiddenSelect, { target: { value: 'B' } })
    
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
    expect(screen.getByRole('button', { name: /traitement en cours/i })).toBeDisabled()
  })

  it('test_time_field_validation', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<UploadForm onSubmit={onSubmit} />)

    await user.upload(screen.getByLabelText('GTFS ZIP'), gtfsFile)
    
    const debutInput = screen.getByLabelText(/HP matin début/i)
    const finInput = screen.getByLabelText(/HP matin fin/i)
    
    await user.clear(debutInput)
    await user.type(debutInput, '10:00')
    await user.clear(finInput)
    await user.type(finInput, '09:00')
    
    await user.click(screen.getByRole('button', { name: /lancer/i }))
    
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText(/postérieure au début/i)).toBeInTheDocument()

    // Fix it
    await user.clear(finInput)
    await user.type(finInput, '11:00')
    await user.click(screen.getByRole('button', { name: /lancer/i }))
    
    expect(screen.queryByText(/postérieure au début/i)).not.toBeInTheDocument()
    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('test_upload_form_drag_zone_exists', () => {
    const { container } = render(<UploadForm onSubmit={vi.fn()} />)
    const dragZone = container.querySelector('.border-dashed')
    expect(dragZone).toBeInTheDocument()
  })
})
