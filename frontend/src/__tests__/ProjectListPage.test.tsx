import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProjectListPage } from '../pages/ProjectListPage';
import * as apiClient from '../api/client';
import type { ProjectResponse } from '../types/api';

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
    render(<ProjectListPage />);
    
    await waitFor(() => {
      expect(screen.getByText('p1')).toBeInTheDocument();
      expect(screen.getByText('p2')).toBeInTheDocument();
    });
  });

  it('test_shows_status_badges', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    render(<ProjectListPage />);
    
    await waitFor(() => {
      expect(screen.getByText('completed')).toBeInTheDocument();
      expect(screen.getByText('processing')).toBeInTheDocument();
    });
  });

  it('test_new_project_button', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    const onNewProjectClick = vi.fn();
    const user = userEvent.setup();
    render(<ProjectListPage onNewProjectClick={onNewProjectClick} />);
    
    await waitFor(() => {
      expect(screen.getByText('p1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /New Project/i }));
    expect(onNewProjectClick).toHaveBeenCalled();
  });

  it('test_empty_state', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue([]);
    render(<ProjectListPage />);
    
    await waitFor(() => {
      expect(screen.getByText(/No projects found/i)).toBeInTheDocument();
    });
  });

  it('test_click_project_navigates', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    const onProjectClick = vi.fn();
    const user = userEvent.setup();
    render(<ProjectListPage onProjectClick={onProjectClick} />);
    
    await waitFor(() => {
      expect(screen.getByText('p1')).toBeInTheDocument();
    });

    await user.click(screen.getByText('p1'));
    expect(onProjectClick).toHaveBeenCalledWith('p1');
  });
});
