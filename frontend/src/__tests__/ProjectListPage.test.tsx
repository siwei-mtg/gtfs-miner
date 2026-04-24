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
  deleteProject: vi.fn(),
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

    await user.click(screen.getByRole('button', { name: /Nouveau projet/i }));
    expect(onNewProjectClick).toHaveBeenCalled();
  });

  it('test_empty_state', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue([]);
    renderWithRouter(<ProjectListPage />);

    await waitFor(() => {
      expect(screen.getByText(/Aucun projet/i)).toBeInTheDocument();
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

  // Refonte : le badge de statut est maintenant une Pastille éditoriale
  // adjacente au libellé. Vérifie juste que le libellé s'affiche distinctement.
  it('test_project_list_status_rendered', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    renderWithRouter(<ProjectListPage />);

    await waitFor(() => {
      expect(screen.getByText('completed')).toBeInTheDocument();
      expect(screen.getByText('processing')).toBeInTheDocument();
    });
  });

  it('test_project_list_search_filters_rows', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage />);

    await waitFor(() => {
      expect(screen.getByText('p1')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Rechercher un ID projet/i);
    await user.type(searchInput, 'nonexistent-xyz');

    expect(screen.queryByText('p1')).not.toBeInTheDocument();
    expect(screen.queryByText('p2')).not.toBeInTheDocument();
  });

  // ──────────────────────────────────────────────────────────────────
  // Delete flow
  // ──────────────────────────────────────────────────────────────────

  it('test_delete_button_rendered_per_row', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    renderWithRouter(<ProjectListPage />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /Supprimer le projet p1/i }),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: /Supprimer le projet p2/i }),
    ).toBeInTheDocument();
  });

  it('test_delete_button_disabled_for_processing_project', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    renderWithRouter(<ProjectListPage />);

    const btn = await screen.findByRole('button', {
      name: /Supprimer le projet p2/i,
    });
    expect(btn).toBeDisabled();
  });

  it('test_delete_click_opens_confirm_dialog', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage />);

    const btn = await screen.findByRole('button', {
      name: /Supprimer le projet p1/i,
    });
    await user.click(btn);

    expect(
      screen.getByText(/Supprimer définitivement ce projet/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/irrévocablement supprimés/i)).toBeInTheDocument();
  });

  it('test_delete_cancel_does_not_call_api', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage />);

    const btn = await screen.findByRole('button', {
      name: /Supprimer le projet p1/i,
    });
    await user.click(btn);

    await user.click(screen.getByRole('button', { name: /^Annuler$/i }));

    expect(apiClient.deleteProject).not.toHaveBeenCalled();
    expect(screen.getByText('p1')).toBeInTheDocument();
  });

  it('test_delete_confirm_calls_api_and_removes_row', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    vi.mocked(apiClient.deleteProject).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage />);

    const btn = await screen.findByRole('button', {
      name: /Supprimer le projet p1/i,
    });
    await user.click(btn);
    await user.click(
      screen.getByRole('button', { name: /Supprimer définitivement/i }),
    );

    await waitFor(() => {
      expect(apiClient.deleteProject).toHaveBeenCalledWith('p1');
    });
    await waitFor(() => {
      expect(screen.queryByText('p1')).not.toBeInTheDocument();
    });
    // p2 row unaffected.
    expect(screen.getByText('p2')).toBeInTheDocument();
  });

  it('test_delete_success_shows_banner', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    vi.mocked(apiClient.deleteProject).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage />);

    const btn = await screen.findByRole('button', {
      name: /Supprimer le projet p1/i,
    });
    await user.click(btn);
    await user.click(
      screen.getByRole('button', { name: /Supprimer définitivement/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/supprimé/i);
    });
  });

  it('test_delete_failure_shows_error_banner', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    vi.mocked(apiClient.deleteProject).mockRejectedValue(
      new Error('deleteProject failed: 500'),
    );
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage />);

    const btn = await screen.findByRole('button', {
      name: /Supprimer le projet p1/i,
    });
    await user.click(btn);
    await user.click(
      screen.getByRole('button', { name: /Supprimer définitivement/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /La suppression a échoué/i,
      );
    });
    expect(screen.getByText('p1')).toBeInTheDocument();
  });

  it('test_delete_conflict_shows_processing_error', async () => {
    vi.mocked(apiClient.listProjects).mockResolvedValue(mockProjects);
    vi.mocked(apiClient.deleteProject).mockRejectedValue(
      new Error('deleteProject failed: 409'),
    );
    const user = userEvent.setup();
    renderWithRouter(<ProjectListPage />);

    const btn = await screen.findByRole('button', {
      name: /Supprimer le projet p1/i,
    });
    await user.click(btn);
    await user.click(
      screen.getByRole('button', { name: /Supprimer définitivement/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /projet en cours de traitement/i,
      );
    });
  });
});
