import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ResultTable } from '../components/ResultTable';
import * as apiClient from '../api/client';

vi.mock('../api/client', () => ({
  getTableData: vi.fn(),
  getTableDownloadUrl: vi.fn(),
}));

const mockData = {
  total: 105,
  columns: ['id', 'name', 'value'],
  rows: [
    { id: 1, name: 'Test 1', value: 'A' },
    { id: 2, name: 'Test 2', value: 'B' }
  ]
};

describe('ResultTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getTableDownloadUrl).mockReturnValue('/download/url');
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

  it('test_loading_state', async () => {
    // Return a promise that doesn't resolve immediately
    vi.mocked(apiClient.getTableData).mockReturnValue(new Promise(() => {}));
    
    render(<ResultTable projectId="p1" tableName="t1" />);
    expect(screen.getByText(/Loading table data/i)).toBeInTheDocument();
  });

  it('test_search_input', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const user = userEvent.setup();
    render(<ResultTable projectId="p1" tableName="t1" />);
    
    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());

    const searchInput = screen.getByLabelText(/Search/i);
    await user.type(searchInput, 'hello');
    await user.click(screen.getByRole('button', { name: /search/i }));

    expect(getTableMock).toHaveBeenLastCalledWith('p1', 't1', expect.objectContaining({ q: 'hello', skip: 0 }));
  });

  it('test_pagination_controls', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const user = userEvent.setup();
    render(<ResultTable projectId="p1" tableName="t1" />);
    
    await waitFor(() => expect(screen.getByText('id')).toBeInTheDocument());

    // Next page
    await user.click(screen.getByRole('button', { name: /Next/i }));
    expect(getTableMock).toHaveBeenLastCalledWith('p1', 't1', expect.objectContaining({ skip: 50 }));

    // Change limit
    const limitSelect = screen.getByLabelText(/Rows per page/i);
    await user.selectOptions(limitSelect, '100');
    expect(getTableMock).toHaveBeenLastCalledWith('p1', 't1', expect.objectContaining({ limit: 100, skip: 0 }));
  });

  it('test_sort_on_header_click', async () => {
    const getTableMock = vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    const user = userEvent.setup();
    render(<ResultTable projectId="p1" tableName="t1" />);
    
    await waitFor(() => expect(screen.getByText('name')).toBeInTheDocument());

    // Setup initial sort
    await user.click(screen.getByText('name'));
    expect(getTableMock).toHaveBeenLastCalledWith('p1', 't1', expect.objectContaining({ sort_by: 'name', sort_order: 'asc' }));

    // Reverse sort
    await user.click(screen.getByText('name ↑'));
    expect(getTableMock).toHaveBeenLastCalledWith('p1', 't1', expect.objectContaining({ sort_by: 'name', sort_order: 'desc' }));
  });

  it('test_download_button_per_table', async () => {
    vi.mocked(apiClient.getTableData).mockResolvedValue(mockData);
    render(<ResultTable projectId="p1" tableName="t1" />);
    
    await waitFor(() => {
      const downloadBtn = screen.getByRole('link', { name: /Download CSV/i });
      expect(downloadBtn).toHaveAttribute('href', '/download/url');
    });
  });
});
