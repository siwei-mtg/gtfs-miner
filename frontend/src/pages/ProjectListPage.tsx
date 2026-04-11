import React, { useEffect, useState } from 'react';
import { listProjects } from '../api/client';
import type { ProjectResponse } from '../types/api';

interface ProjectListPageProps {
  onProjectClick?: (id: string) => void;
  onNewProjectClick?: () => void;
}

export const ProjectListPage: React.FC<ProjectListPageProps> = ({ 
  onProjectClick, 
  onNewProjectClick 
}) => {
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);
    listProjects()
      .then(data => {
        if (mounted) {
          setProjects(data);
          setError(null);
        }
      })
      .catch(err => {
        if (mounted) {
          setError('Failed to load projects');
        }
      })
      .finally(() => {
        if (mounted) {
          setIsLoading(false);
        }
      });
    return () => { mounted = false; };
  }, []);

  const handleProjectClick = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    if (onProjectClick) {
      onProjectClick(id);
    } else {
      window.location.href = `/projects/${id}`;
    }
  };

  const renderBadge = (status: string) => {
    return <span className={`badge badge-${status}`}>{status}</span>;
  };

  if (isLoading) {
    return <div>Loading projects...</div>;
  }

  if (error) {
    return <div role="alert">{error}</div>;
  }

  return (
    <div className="project-list-container">
      <div className="header">
        <h2>My Projects</h2>
        <button onClick={onNewProjectClick}>New Project</button>
      </div>

      {projects.length === 0 ? (
        <div className="empty-state">No projects found. Create one to get started.</div>
      ) : (
        <ul className="project-list">
          {projects.map(project => (
            <li key={project.id} className="project-item">
              <a href={`/projects/${project.id}`} onClick={(e) => handleProjectClick(e, project.id)}>
                <span className="project-id">{project.id}</span>
                {renderBadge(project.status)}
                <span className="project-date">{new Date(project.created_at).toLocaleString()}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
