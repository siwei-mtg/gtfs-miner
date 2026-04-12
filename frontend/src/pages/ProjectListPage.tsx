import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listProjects } from '../api/client';
import type { ProjectResponse } from '../types/api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/atoms/badge';
import { Button } from '@/components/atoms/button';
import { Input } from '@/components/atoms/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface ProjectListPageProps {
  onProjectClick?: (id: string) => void;
  onNewProjectClick?: () => void;
}

type BadgeVariant = 'default' | 'destructive' | 'secondary' | 'outline';

const statusVariantMap: Record<string, BadgeVariant> = {
  completed: 'default',
  failed: 'destructive',
  processing: 'secondary',
  pending: 'outline',
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
    } else {
      navigate(`/projects/${id}`);
    }
  };

  const handleNewProject = () => {
    if (onNewProjectClick) {
      onNewProjectClick();
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
    return <div>Loading projects...</div>;
  }

  if (error) {
    return <div role="alert">{error}</div>;
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1">
          <Input
            placeholder="搜索项目 ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-xs"
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="所有状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">所有状态</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button onClick={handleNewProject}>新建项目</Button>
      </div>

      {/* Table */}
      {filteredProjects.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          No projects found. Create one to get started.
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>项目 ID</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProjects.map((project) => (
                <TableRow key={project.id}>
                  <TableCell className="font-mono text-sm">
                    <a
                      href={`/projects/${project.id}`}
                      onClick={(e) => handleProjectClick(e, project.id)}
                      className="hover:underline"
                    >
                      {project.id}
                    </a>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={statusVariantMap[project.status] ?? 'outline'}
                    >
                      {project.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {new Date(project.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      asChild
                    >
                      <a
                        href={`/projects/${project.id}`}
                        onClick={(e) => handleProjectClick(e, project.id)}
                      >
                        查看
                      </a>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
};
