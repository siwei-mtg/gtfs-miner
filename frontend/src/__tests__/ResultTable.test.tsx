import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ResultTable } from '@/components/organisms/ResultTable';
import * as apiClient from '../api/client';

vi.mock('../api/client', () => ({
  getTableData: vi.fn(),
  downloadTableCsv: vi.fn(),
}));

// Radix Select only renders a hidden <select> when inside a <form>.
// Mock it with a plain native select so tests can interact with it normally.
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

const mockData = {
  total: 105,
  columns: ['id', 'name', 'value'],
  rows: [
    { id: 1, name: 'Test 1', value: 'A' },
    { id: 2, name: 'Test 2', value: 'B' },
  ],
};

describe('ResultTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.downloadTableCsv).mockResolvedValue(undefined);
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

  it('test_pagination_controls', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const user = userEvent.setup();
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());

    // Next page — shadcn PaginationNext renders as <a aria-label="Go to next page"> (no href → not role=link)
    await user.click(screen.getByLabelText(/Go to next page/i));
    expect(getTableMock).toHaveBeenLastCalledWith(
      'p1', 't1', expect.objectContaining({ skip: 50 }),
    );

    // Change limit — mocked Select renders a plain <select aria-label="Rows per page">
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

    // First click: ascending sort
    await user.click(screen.getByRole('button', { name: 'name' }));
    expect(getTableMock).toHaveBeenLastCalledWith(
      'p1', 't1', expect.objectContaining({ sort_by: 'name', sort_order: 'asc' }),
    );

    // Second click: reverse sort (SVG icon has aria-hidden so button name stays 'name')
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

  // ── New tests for Task 45 ──────────────────────────────────────────────

  it('test_result_table_renders_shadcn_header', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);

    // shadcn TableHead renders <th role="columnheader">
    await waitFor(() => {
      const columnHeaders = screen.getAllByRole('columnheader');
      expect(columnHeaders.length).toBe(3); // id, name, value
    });
  });

  it('test_result_table_sort_toggle_icon', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const user = userEvent.setup();
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'name' })).toBeInTheDocument());

    // No sort icon before clicking
    expect(screen.getByRole('button', { name: 'name' }).querySelector('svg')).toBeNull();

    // Click → triggers API reload; wait for table to re-appear, then check for SVG
    await user.click(screen.getByRole('button', { name: 'name' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'name' }).querySelector('svg')).toBeInTheDocument();
    });

    // Click again → descending; re-query after reload
    await user.click(screen.getByRole('button', { name: 'name' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'name' }).querySelector('svg')).toBeInTheDocument();
    });
  });

  it('test_result_table_pagination_prev_next', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);

    await waitFor(() => {
      // shadcn PaginationPrevious renders <a aria-label="Go to previous page"> (no href)
      expect(screen.getByLabelText(/Go to previous page/i)).toBeInTheDocument();
      // shadcn PaginationNext renders <a aria-label="Go to next page"> (no href)
      expect(screen.getByLabelText(/Go to next page/i)).toBeInTheDocument();
    });
  });
});
