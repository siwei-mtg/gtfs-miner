import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Pastille } from '@/components/atoms/Pastille'
import { CodeTag } from '@/components/atoms/CodeTag'
import { Hairline } from '@/components/atoms/Hairline'
import { EditorialStat } from '@/components/molecules/EditorialStat'

describe('Design system — signature atoms', () => {
  it('Pastille renders letter and applies tone class', () => {
    render(<Pastille tone="signal">A</Pastille>)
    const el = screen.getByText('A')
    expect(el.className).toMatch(/bg-signal/)
    expect(el.className).toMatch(/font-mono/)
  })

  it('Pastille supports 7 GTFS route_type tones', () => {
    const tones = ['tram', 'metro', 'rail', 'bus', 'ferry', 'cable', 'funicular'] as const
    tones.forEach((t) => {
      const { unmount } = render(<Pastille tone={t}>{t[0].toUpperCase()}</Pastille>)
      const el = screen.getByText(t[0].toUpperCase())
      expect(el.className).toMatch(new RegExp(`bg-rt-${t}`))
      unmount()
    })
  })

  it('CodeTag wraps children in a <code> with mono font', () => {
    render(<CodeTag>proj-123</CodeTag>)
    const el = screen.getByText('proj-123')
    expect(el.tagName).toBe('CODE')
    expect(el.className).toMatch(/font-mono/)
  })

  it('Hairline exposes role="separator" with orientation', () => {
    render(<Hairline orientation="vertical" data-testid="hair" />)
    const el = screen.getByTestId('hair')
    expect(el.getAttribute('role')).toBe('separator')
    expect(el.getAttribute('aria-orientation')).toBe('vertical')
  })

  it('EditorialStat formats numeric value in fr-FR tabular-nums', () => {
    render(<EditorialStat label="Lignes" value={1234567} />)
    // 1234567 → "1 234 567" (espaces insécables en fr-FR)
    const el = screen.getByText((txt) => /1[\u00A0\u202F ]234[\u00A0\u202F ]567/.test(txt))
    expect(el).toBeInTheDocument()
    expect(el.className).toMatch(/tabular-nums/)
    expect(el.className).toMatch(/font-display/)
  })

  it('EditorialStat shows skeleton when loading', () => {
    render(<EditorialStat label="Lignes" value={42} loading />)
    expect(screen.queryByText('42')).not.toBeInTheDocument()
  })
})
