import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { ProjectListPage } from '../pages/ProjectListPage';
import * as apiClient from '../api/client';
import type { ProjectResponse } from '../types/api';

const renderWithRouter = (ui: React.ReactElement) =>
  render(<MemoryRouter>{ui}</MemoryRouter>);

vi.mock('../api/client', () => ({
  listProjects: vi.fn(),
}));

const mockProjects: ProjectResponse[] = [
  {
    id: 'p1',
    status: 'completed',
    created_at: '2026-04-10T10:00:00Z',
    updated_at: '2026-04-10T11:00:00Z',
    parameters: {} as any,
    error_message: null
  },
  {
    id: 'p2',
    status: 'processing',
    created_at: '2026-04-11T12:00:00Z',
    updated_at: '2026-04-11T12:00:00Z',
    parameters: {} as any,
    error_message: null
  }
];

describe('ProjectListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('test_renders_project_list', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    renderWithRouter(<ProjectListPage />);
    
    await waitFor(() => {
      expect(screen.getByText('p1')).toBeInTheDocument();
      expect(screen.getByText('p2')).toBeInTheDocument();
    });
  });

  it('test_shows_status_badges', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    renderWithRouter(<ProjectListPage />);
    
    await waitFor(() => {
      expect(screen.getByText('completed')).toBeInTheDocument();
      expect(screen.getByText('processing')).toBeInTheDocument();
    });
  });

  it('test_new_project_button', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    const onNewProjectClick = vi.fn();
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage onNewProjectClick={onNewProjectClick} />);
    
    await waitFor(() => {
      expect(screen.getByText('p1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /新建项目/i }));
    expect(onNewProjectClick).toHaveBeenCalled();
  });

  it('test_empty_state', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue([]);
    renderWithRouter(<ProjectListPage />);
    
    await waitFor(() => {
      expect(screen.getByText(/No projects found/i)).toBeInTheDocument();
    });
  });

  it('test_click_project_navigates', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    const onProjectClick = vi.fn();
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage onProjectClick={onProjectClick} />);
    
    await waitFor(() => {
      expect(screen.getByText('p1')).toBeInTheDocument();
    });

    await user.click(screen.getByText('p1'));
    expect(onProjectClick).toHaveBeenCalledWith('p1');
  });

  // Task 43
  it('test_project_list_badge_completed_green', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    renderWithRouter(<ProjectListPage />);

    await waitFor(() => {
      expect(screen.getByText('completed')).toBeInTheDocument();
    });

    // The badge for 'completed' should have the 'default' variant class
    const completedBadge = screen.getByText('completed');
    expect(completedBadge.className).toMatch(/bg-primary/);
  });

  it('test_project_list_search_filters_rows', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage />);

    await waitFor(() => {
      expect(screen.getByText('p1')).toBeInTheDocument();
    });

    // Type a non-existent project ID in the search box
    const searchInput = screen.getByPlaceholderText('搜索项目 ID...');
    await user.type(searchInput, 'nonexistent-xyz');

    // Both rows should be filtered out
    expect(screen.queryByText('p1')).not.toBeInTheDocument();
    expect(screen.queryByText('p2')).not.toBeInTheDocument();
  });
});
