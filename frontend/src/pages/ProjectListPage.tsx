import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { deleteProject, listProjects } from '../api/client';
import type { ProjectResponse } from '../types/api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/atoms/button';
import { Input } from '@/components/atoms/input';
import { Pastille } from '@/components/atoms/Pastille';
import { CodeTag } from '@/components/atoms/CodeTag';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ConfirmDialog } from '@/components/molecules/ConfirmDialog';
import { Plus, Search, Trash2 } from 'lucide-react';

interface ProjectListPageProps {
  onProjectClick?: (id: string) => void;
  onNewProjectClick?: () => void;
}

type PastilleTone = React.ComponentProps<typeof Pastille>['tone'];

const statusPastille: Record<string, { tone: PastilleTone; dot: string }> = {
  completed: { tone: 'default', dot: '●' },
  failed: { tone: 'destructive', dot: '▲' },
  processing: { tone: 'signal', dot: '◐' },
  pending: { tone: 'muted', dot: '○' },
};

const fmtYmd = (n: number | null): string => {
  if (!n) return '';
  const s = String(n);
  return `${s.slice(6, 8)}/${s.slice(4, 6)}/${s.slice(0, 4)}`;
};

const fmtValidite = (deb: number | null, fin: number | null): string | null => {
  if (!deb || !fin) return null;
  return `${fmtYmd(deb)} – ${fmtYmd(fin)}`;
};

export const ProjectListPage: React.FC<ProjectListPageProps> = ({
  onProjectClick,
  onNewProjectClick,
}) => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [pendingDelete, setPendingDelete] = useState<ProjectResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!deleteSuccess) return;
    const id = window.setTimeout(() => setDeleteSuccess(null), 3000);
    return () => window.clearTimeout(id);
  }, [deleteSuccess]);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);
    listProjects()
      .then((data) => {
        if (mounted) {
          setProjects(data);
          setError(null);
        }
      })
      .catch(() => {
        if (mounted) {
          setError('Failed to load projects');
        }
      })
      .finally(() => {
        if (mounted) {
          setIsLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const handleProjectClick = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    if (onProjectClick) {
      onProjectClick(id);
      return;
    }
    navigate(`/projects/${id}`);
  };

  const handleNewProject = () => {
    if (onNewProjectClick) {
      onNewProjectClick();
    }
  };

  const handleDeleteClick = (project: ProjectResponse) => {
    setDeleteError(null);
    setPendingDelete(project);
  };

  const handleConfirmDelete = async () => {
    if (!pendingDelete) return;
    setIsDeleting(true);
    try {
      await deleteProject(pendingDelete.id);
      setProjects((prev) => prev.filter((p) => p.id !== pendingDelete.id));
      setDeleteError(null);
      setDeleteSuccess('Projet supprimé avec succès.');
      setPendingDelete(null);
    } catch (err) {
      const isConflict =
        err instanceof Error && err.message.includes('409');
      setDeleteSuccess(null);
      setDeleteError(
        isConflict
          ? 'Impossible de supprimer un projet en cours de traitement.'
          : 'La suppression a échoué. Réessayez.',
      );
      setPendingDelete(null);
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      searchQuery === '' ||
      p.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  if (isLoading) {
    return (
      <div className="px-6 py-10 text-sm text-ink-muted">
        Chargement des projets…
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="px-6 py-10 text-sm text-destructive">
        {error}
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-6 py-8">
      {/* Page header éditorial */}
      <header className="flex items-end justify-between gap-4 border-b border-hair pb-4">
        <div>
          <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-ink-muted">
            Projets GTFS
          </span>
          <h1 className="mt-1 font-display text-[36px] font-medium leading-none text-ink">
            Mes projets
          </h1>
        </div>
        <Button onClick={handleNewProject} className="gap-2">
          <Plus className="h-4 w-4" />
          Nouveau projet
        </Button>
      </header>

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
          <Input
            placeholder="Rechercher un ID projet…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Tous les statuts" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les statuts</SelectItem>
            <SelectItem value="completed">Terminés</SelectItem>
            <SelectItem value="processing">En cours</SelectItem>
            <SelectItem value="pending">En attente</SelectItem>
            <SelectItem value="failed">Échec</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {deleteError && (
        <div
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive"
        >
          {deleteError}
        </div>
      )}

      {deleteSuccess && (
        <div
          role="status"
          className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-700 dark:text-emerald-300"
        >
          {deleteSuccess}
        </div>
      )}

      {/* Table éditoriale */}
      {filteredProjects.length === 0 ? (
        <div className="rounded-lg border border-hair bg-card px-6 py-16 text-center">
          <p className="font-display text-lg text-ink">Aucun projet.</p>
          <p className="mt-1 text-sm text-ink-muted">
            Créez votre premier projet pour commencer l'analyse GTFS.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-hair bg-card">
          <Table>
            <TableHeader>
              <TableRow className="border-hair">
                <TableHead className="text-[10px] uppercase tracking-[0.15em] text-ink-muted">
                  ID projet
                </TableHead>
                <TableHead className="text-[10px] uppercase tracking-[0.15em] text-ink-muted">
                  Réseau
                </TableHead>
                <TableHead className="text-[10px] uppercase tracking-[0.15em] text-ink-muted">
                  Validité
                </TableHead>
                <TableHead className="text-[10px] uppercase tracking-[0.15em] text-ink-muted">
                  Statut
                </TableHead>
                <TableHead className="text-[10px] uppercase tracking-[0.15em] text-ink-muted">
                  Créé le
                </TableHead>
                <TableHead className="text-right text-[10px] uppercase tracking-[0.15em] text-ink-muted">
                  Action
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProjects.map((project) => {
                const config = statusPastille[project.status] ?? {
                  tone: 'muted' as const,
                  dot: '·',
                };
                const href = `/projects/${project.id}`;
                return (
                  <TableRow
                    key={project.id}
                    className="group border-hair transition-colors hover:bg-secondary/60"
                  >
                    <TableCell>
                      <a
                        href={href}
                        onClick={(e) => handleProjectClick(e, project.id)}
                        className="inline-flex items-center"
                      >
                        <CodeTag className="group-hover:bg-signal/15">
                          {project.id}
                        </CodeTag>
                      </a>
                    </TableCell>
                    <TableCell
                      className="max-w-[14rem] truncate text-sm text-ink"
                      title={project.reseau ?? undefined}
                    >
                      {project.reseau ?? (
                        <span className="text-ink-muted">—</span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs tabular-nums text-ink-muted">
                      {fmtValidite(project.validite_debut, project.validite_fin) ?? (
                        <span className="text-ink-muted">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-2">
                        <Pastille tone={config.tone} size="sm">
                          {config.dot}
                        </Pastille>
                        <span className="text-sm capitalize text-ink">
                          {project.status}
                        </span>
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs tabular-nums text-ink-muted">
                      {new Date(project.created_at).toLocaleString('fr-FR', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="inline-flex items-center gap-1">
                        <Button variant="ghost" size="sm" asChild>
                          <a
                            href={href}
                            onClick={(e) => handleProjectClick(e, project.id)}
                          >
                            Ouvrir →
                          </a>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteClick(project)}
                          disabled={project.status === 'processing'}
                          aria-label={`Supprimer le projet ${project.id}`}
                          title={
                            project.status === 'processing'
                              ? 'Impossible de supprimer un projet en cours'
                              : 'Supprimer définitivement'
                          }
                          className="text-ink-muted hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
        title="Supprimer définitivement ce projet ?"
        description={
          <>
            Le projet{' '}
            {pendingDelete && <CodeTag>{pendingDelete.id}</CodeTag>} et
            toutes ses données (tables de résultats, fichiers d'export,
            historique de progression) seront{' '}
            <strong>irrévocablement supprimés</strong>. Cette action est
            permanente.
          </>
        }
        confirmLabel="Supprimer définitivement"
        cancelLabel="Annuler"
        loadingLabel="Suppression en cours…"
        destructive
        loading={isDeleting}
        onConfirm={handleConfirmDelete}
      />
    </div>
  );
};
