import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DownloadButton } from '../components/DownloadButton'

describe('DownloadButton', () => {
  it('renders disabled button when projectId is null', () => {
    render(<DownloadButton projectId={null} />)
    expect(screen.getByLabelText('download-button')).toBeDisabled()
  })

  it('renders disabled button when disabled prop is true', () => {
    render(<DownloadButton projectId="proj-1" disabled />)
    expect(screen.getByLabelText('download-button')).toBeDisabled()
  })

  it('renders an anchor with correct href when enabled', () => {
    render(<DownloadButton projectId="proj-1" />)
    const link = screen.getByLabelText('download-button')
    expect(link.tagName).toBe('A')
    expect(link).toHaveAttribute('href', '/api/v1/projects/proj-1/download')
  })

  it('anchor has download attribute', () => {
    render(<DownloadButton projectId="proj-1" />)
    expect(screen.getByLabelText('download-button')).toHaveAttribute('download')
  })
})
