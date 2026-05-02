import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ResultTable } from '@/components/organisms/ResultTable';
import type { ColumnFilter } from '@/types/api';
import * as apiClient from '../api/client';

vi.mock('../api/client', () => ({
  getTableData: vi.fn(),
  downloadTableCsv: vi.fn(),
  getColumnDistinct: vi.fn(),
}));

// Radix Select only renders a hidden <select> when inside a <form>.
// Mock with a native select so tests can interact with it normally.
vi.mock('@/components/ui/select', () => ({
  Select: ({ onValueChange, value, name, children }: any) => (
    <select
      name={name}
      value={value}
      aria-label="Rows per page"
      onChange={(e) => onValueChange(e.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: any) => <>{children}</>,
  SelectValue: () => null,
  SelectContent: ({ children }: any) => <>{children}</>,
  SelectItem: ({ value, children }: any) => <option value={value}>{children}</option>,
}));

// Radix Popover uses portals + non-interactive defaults that fight JSDOM.
// Render trigger only, swallow the (closed) popover content so we never
// instantiate cmdk (which needs ResizeObserver).
vi.mock('@/components/ui/popover', () => ({
  Popover: ({ children }: any) => <>{children}</>,
  PopoverTrigger: ({ children }: any) => <>{children}</>,
  PopoverAnchor: ({ children }: any) => <>{children}</>,
  PopoverContent: () => null,
}));

const mockData = {
  total: 105,
  columns: ['id', 'name', 'value'],
  rows: [
    { id: 1, name: 'Test 1', value: 'A' },
    { id: 2, name: 'Test 2', value: 'B' },
  ],
  column_meta: {
    id: { type: 'numeric' as const, total_distinct: -1 },
    name: { type: 'enum' as const, total_distinct: 2 },
    value: { type: 'enum' as const, total_distinct: 2 },
  },
};

describe('ResultTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.downloadTableCsv).mockResolvedValue(undefined);
    vi.mocked(apiClient.getColumnDistinct).mockResolvedValue({
      values: [],
      total_distinct: 0,
      truncated: false,
    });
  });

  it('test_renders_table_headers', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => {
      expect(screen.getByText('id')).toBeInTheDocument();
      expect(screen.getByText('name')).toBeInTheDocument();
      expect(screen.getByText('value')).toBeInTheDocument();
    });
  });

  it('test_renders_rows', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => {
      expect(screen.getByText('Test 1')).toBeInTheDocument();
      expect(screen.getByText('Test 2')).toBeInTheDocument();
    });
  });

  it('test_shows_total_count', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => {
      expect(screen.getByText(/Total rows: 105/i)).toBeInTheDocument();
    });
  });

  it('test_loading_state', () => {
    vi.mocked(apiClient.getTableData).mockReturnValue(new Promise(() => {}));
    render(<ResultTable projectId="p1" tableName="t1" />);
    expect(screen.getByText(/Loading table data/i)).toBeInTheDocument();
  });

  it('requests column_meta on every fetch', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => {
      expect(getTableMock).toHaveBeenCalledWith(
        'p1', 't1', expect.objectContaining({ column_meta: true }),
      );
    });
  });

  it('renders one filter trigger per column', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => {
      const triggers = screen.getAllByRole('button', { name: /Filtrer la colonne|Filtre actif/ });
      expect(triggers.length).toBe(3);
    });
  });

  it('test_pagination_controls', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const user = userEvent.setup();
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());

    await user.click(screen.getByLabelText(/Go to next page/i));
    expect(getTableMock).toHaveBeenLastCalledWith(
      'p1', 't1', expect.objectContaining({ skip: 50 }),
    );

    const limitSelect = screen.getByRole('combobox', { name: /Rows per page/i });
    await user.selectOptions(limitSelect, '100');
    expect(getTableMock).toHaveBeenLastCalledWith(
      'p1', 't1', expect.objectContaining({ limit: 100, skip: 0 }),
    );
  });

  it('test_sort_on_header_click', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const user = userEvent.setup();
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => expect(screen.getByText('name')).toBeInTheDocument());

    await user.click(screen.getByRole('button', { name: 'name' }));
    expect(getTableMock).toHaveBeenLastCalledWith(
      'p1', 't1', expect.objectContaining({ sort_by: 'name', sort_order: 'asc' }),
    );

    await user.click(screen.getByRole('button', { name: 'name' }));
    expect(getTableMock).toHaveBeenLastCalledWith(
      'p1', 't1', expect.objectContaining({ sort_by: 'name', sort_order: 'desc' }),
    );
  });

  it('test_download_button_per_table', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => {
      const downloadBtn = screen.getByRole('button', { name: /Download CSV/i });
      expect(downloadBtn).toBeInTheDocument();
    });
  });

  it('externalColumnFilters seed the API call as multi-filter params', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const external: Record<string, ColumnFilter> = {
      route_type: { kind: 'in', values: ['3'] },
    };
    render(
      <ResultTable
        projectId="p1"
        tableName="b1"
        externalColumnFilters={external}
      />,
    );

    await waitFor(() => {
      const lastCall = getTableMock.mock.calls.at(-1);
      expect(lastCall?.[2].filters).toMatchObject({
        route_type: { kind: 'in', values: ['3'] },
      });
    });
  });

  it('chip ✕ removes the matching filter and re-fetches', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const user = userEvent.setup();
    const external: Record<string, ColumnFilter> = {
      route_type: { kind: 'in', values: ['3'] },
    };
    render(
      <ResultTable projectId="p1" tableName="b1" externalColumnFilters={external} />,
    );

    await waitFor(() =>
      expect(getTableMock).toHaveBeenCalledWith(
        'p1', 'b1', expect.objectContaining({ filters: { route_type: { kind: 'in', values: ['3'] } } }),
      ),
    );

    await user.click(screen.getByLabelText(/Retirer le filtre route_type/));

    await waitFor(() => {
      const lastCall = getTableMock.mock.calls.at(-1);
      expect(lastCall?.[2].filters).toEqual({});
    });
  });

  it('lifts onFilterChange for mapped columns when filter clears', async () => {
    // Mount-time + mirror-sync should NOT lift back to context (that was the
    // regression behind the dashboard-linkage bug).  Only the user clicking
    // the chip ✕ should emit an empty routeTypes payload.
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const onFilterChange = vi.fn();
    const external: Record<string, ColumnFilter> = {
      route_type: { kind: 'in', values: ['3'] },
    };
    const user = userEvent.setup();
    render(
      <ResultTable
        projectId="p1"
        tableName="b1"
        externalColumnFilters={external}
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());
    expect(onFilterChange).not.toHaveBeenCalled();

    await user.click(screen.getByLabelText(/Retirer le filtre route_type/));

    await waitFor(() => {
      const lastEmit = onFilterChange.mock.calls.at(-1)?.[0];
      expect(lastEmit?.routeTypes).toEqual([]);
    });
  });

  it('does not lift onFilterChange on mount or when only external filters change', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const onFilterChange = vi.fn();
    const { rerender } = render(
      <ResultTable
        projectId="p1"
        tableName="f1"
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());
    expect(onFilterChange).not.toHaveBeenCalled();

    // Mirroring an external filter in must not leak back as a lift-up.
    const external: Record<string, ColumnFilter> = {
      route_type: { kind: 'in', values: ['3'] },
    };
    rerender(
      <ResultTable
        projectId="p1"
        tableName="f1"
        externalColumnFilters={external}
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => {
      const lastCall = vi.mocked(apiClient.getTableData).mock.calls.at(-1);
      expect(lastCall?.[2].filters).toMatchObject({
        route_type: { kind: 'in', values: ['3'] },
      });
    });
    expect(onFilterChange).not.toHaveBeenCalled();
  });

  it('emits only the touched slot, not all three', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const onFilterChange = vi.fn();
    const external: Record<string, ColumnFilter> = {
      id_ligne_num: { kind: 'in', values: ['42'] },
    };
    const user = userEvent.setup();
    render(
      <ResultTable
        projectId="p1"
        tableName="b2"
        externalColumnFilters={external}
        onFilterChange={onFilterChange}
      />,
    );

    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());

    await user.click(screen.getByLabelText(/Retirer le filtre id_ligne_num/));

    await waitFor(() => expect(onFilterChange).toHaveBeenCalled());
    const lastEmit = onFilterChange.mock.calls.at(-1)?.[0];
    expect(Object.keys(lastEmit ?? {})).toEqual(['ligneIds']);
    expect(lastEmit?.ligneIds).toEqual([]);
  });

  it('lifts the FULL filter map via onAllColumnFiltersChange when the user removes a filter', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const onAllColumnFiltersChange = vi.fn();
    const external: Record<string, ColumnFilter> = {
      route_long_name: { kind: 'in', values: ['Ligne 1'] },
    };
    const user = userEvent.setup();
    render(
      <ResultTable
        projectId="p1"
        tableName="b2"
        externalColumnFilters={external}
        onAllColumnFiltersChange={onAllColumnFiltersChange}
      />,
    );

    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());
    // Mount must not lift (mirror is not user-action).
    expect(onAllColumnFiltersChange).not.toHaveBeenCalled();

    await user.click(screen.getByLabelText(/Retirer le filtre route_long_name/));

    await waitFor(() => expect(onAllColumnFiltersChange).toHaveBeenCalled());
    expect(onAllColumnFiltersChange.mock.calls.at(-1)?.[0]).toEqual({});
  });

  it('filters reset when tableName changes', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const external: Record<string, ColumnFilter> = {
      route_type: { kind: 'in', values: ['3'] },
    };
    const { rerender } = render(
      <ResultTable projectId="p1" tableName="b1" externalColumnFilters={external} />,
    );

    await waitFor(() =>
      expect(getTableMock).toHaveBeenLastCalledWith(
        'p1', 'b1', expect.objectContaining({ filters: { route_type: { kind: 'in', values: ['3'] } } }),
      ),
    );

    rerender(<ResultTable projectId="p1" tableName="f1" />);

    await waitFor(() => {
      const lastCall = getTableMock.mock.calls.at(-1);
      expect(lastCall?.[1]).toBe('f1');
      expect(lastCall?.[2].filters).toEqual({});
    });
  });
});
