import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ColumnFilterPopover } from '@/components/molecules/ColumnFilterPopover'
import * as apiClient from '@/api/client'

vi.mock('@/api/client', () => ({
  getColumnDistinct: vi.fn(),
}))

// Stub out Radix Popover with a state-aware mock so the popover content only
// renders once the trigger is clicked (matches Radix semantics + lets the
// fetch effect run with open=true).
vi.mock('@/components/ui/popover', async () => {
  const React = await import('react')
  const Ctx = React.createContext<{ open: boolean; setOpen: (v: boolean) => void } | null>(null)
  return {
    Popover: ({ children, open, onOpenChange }: any) => (
      <Ctx.Provider value={{ open, setOpen: onOpenChange }}>{children}</Ctx.Provider>
    ),
    PopoverTrigger: ({ children }: any) => {
      const ctx = React.useContext(Ctx)
      return (
        <span
          role="presentation"
          onClick={() => ctx?.setOpen(!ctx.open)}
          data-testid="popover-trigger-wrap"
        >
          {children}
        </span>
      )
    },
    PopoverContent: ({ children }: any) => {
      const ctx = React.useContext(Ctx)
      return ctx?.open ? <div role="dialog">{children}</div> : null
    },
    PopoverAnchor: ({ children }: any) => <>{children}</>,
  }
})

const Trigger = (
  <button type="button" data-testid="trigger">
    funnel
  </button>
)

describe('ColumnFilterPopover', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('numeric layout — Apply emits a range from min/max inputs', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <ColumnFilterPopover
        projectId="p1"
        tableName="f1"
        column="nb_course"
        dataType="numeric"
        value={null}
        currentSort={null}
        onChange={onChange}
        onSortChange={() => {}}
      >
        {Trigger}
      </ColumnFilterPopover>,
    )

    await user.click(screen.getByTestId('popover-trigger-wrap'))
    const minInput = screen.getByPlaceholderText('min')
    const maxInput = screen.getByPlaceholderText('max')
    await user.type(minInput, '25')
    await user.type(maxInput, '100')
    await user.click(screen.getByRole('button', { name: /Appliquer/i }))

    expect(onChange).toHaveBeenCalledWith({ kind: 'range', min: 25, max: 100 })
  })

  it('numeric layout — Effacer emits null', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <ColumnFilterPopover
        projectId="p1"
        tableName="f1"
        column="nb_course"
        dataType="numeric"
        value={{ kind: 'range', min: 10, max: 50 }}
        currentSort={null}
        onChange={onChange}
        onSortChange={() => {}}
      >
        {Trigger}
      </ColumnFilterPopover>,
    )

    await user.click(screen.getByTestId('popover-trigger-wrap'))
    await user.click(screen.getByRole('button', { name: /Effacer/i }))

    expect(onChange).toHaveBeenCalledWith(null)
  })

  it('enum layout — fetches distinct values then Apply emits in:[…]', async () => {
    vi.mocked(apiClient.getColumnDistinct).mockResolvedValue({
      values: [
        { value: 3, count: 12 },
        { value: 0, count: 4 },
      ],
      total_distinct: 2,
      truncated: false,
    })
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <ColumnFilterPopover
        projectId="p1"
        tableName="b1"
        column="route_type"
        dataType="enum"
        value={null}
        currentSort={null}
        onChange={onChange}
        onSortChange={() => {}}
      >
        {Trigger}
      </ColumnFilterPopover>,
    )

    await user.click(screen.getByTestId('popover-trigger-wrap'))
    await waitFor(() => {
      expect(apiClient.getColumnDistinct).toHaveBeenCalledWith(
        'p1', 'b1', 'route_type', expect.objectContaining({ q: undefined }),
      )
    })

    // Click "Tout cocher" to select both values.
    await user.click(screen.getByRole('button', { name: /Tout cocher/i }))
    await user.click(screen.getByRole('button', { name: /Appliquer/i }))

    expect(onChange).toHaveBeenCalled()
    const emitted = onChange.mock.calls.at(-1)?.[0]
    expect(emitted).toMatchObject({ kind: 'in' })
    expect(new Set(emitted.values)).toEqual(new Set(['3', '0']))
  })

  it('text layout — typing emits a debounced server search', async () => {
    vi.mocked(apiClient.getColumnDistinct).mockResolvedValue({
      values: [],
      total_distinct: 0,
      truncated: false,
    })
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <ColumnFilterPopover
        projectId="p1"
        tableName="a1"
        column="stop_name"
        dataType="text"
        value={null}
        currentSort={null}
        onChange={onChange}
        onSortChange={() => {}}
      >
        {Trigger}
      </ColumnFilterPopover>,
    )

    await user.click(screen.getByTestId('popover-trigger-wrap'))
    const input = screen.getByPlaceholderText('Contient…')
    await user.type(input, 'Gare')

    // Debounce is 250 ms — wait for it to resolve into a fetch with q.
    await waitFor(
      () => {
        expect(apiClient.getColumnDistinct).toHaveBeenCalledWith(
          'p1', 'a1', 'stop_name', expect.objectContaining({ q: 'Gare' }),
        )
      },
      { timeout: 1000 },
    )

    await user.click(screen.getByRole('button', { name: /Appliquer/i }))
    expect(onChange).toHaveBeenCalledWith({ kind: 'contains', term: 'Gare' })
  })

  it('sort header buttons emit onSortChange', async () => {
    const onSortChange = vi.fn()
    const user = userEvent.setup()
    vi.mocked(apiClient.getColumnDistinct).mockResolvedValue({
      values: [],
      total_distinct: 0,
      truncated: false,
    })
    render(
      <ColumnFilterPopover
        projectId="p1"
        tableName="b1"
        column="route_type"
        dataType="enum"
        value={null}
        currentSort={null}
        onChange={() => {}}
        onSortChange={onSortChange}
      >
        {Trigger}
      </ColumnFilterPopover>,
    )

    await user.click(screen.getByTestId('popover-trigger-wrap'))
    await user.click(screen.getByRole('button', { name: /A → Z/ }))
    expect(onSortChange).toHaveBeenCalledWith('asc')

    await user.click(screen.getByRole('button', { name: /Z → A/ }))
    expect(onSortChange).toHaveBeenCalledWith('desc')
  })
})
