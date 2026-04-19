import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ProjectListPage } from './pages/ProjectListPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { DashboardPage } from './pages/DashboardPage'
import { UploadForm } from '@/components/organisms/UploadForm'
import { AppShell } from '@/components/templates/AppShell'
import { createProject, uploadGtfs } from './api/client'
import type { ProjectCreate } from './types/api'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { token, isLoading } = useAuth()
  if (isLoading) return <div>Loading session...</div>
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function NewProjectPage() {
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function handleSubmit(file: File, params: ProjectCreate) {
    setUploadError(null)
    setIsUploading(true)
    try {
      const project = await createProject(params)
      await uploadGtfs(project.id, file)
      navigate(`/projects/${project.id}`)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Erreur inattendue')
      setIsUploading(false)
    }
  }

  return (
    <div>
      <h2>New Project</h2>
      <button onClick={() => navigate('/')}>&larr; Back to Projects</button>
      <UploadForm
        onSubmit={handleSubmit}
        isLoading={isUploading}
        error={uploadError}
      />
    </div>
  )
}

function App() {
  const { user, logout } = useAuth()
  return (
    <BrowserRouter>
      <AppShell user={user} onLogout={logout}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route path="/" element={
            <AuthGuard>
              <ProjectListContainer />
            </AuthGuard>
          } />

          <Route path="/new" element={
            <AuthGuard>
              <NewProjectPage />
            </AuthGuard>
          } />

          <Route path="/projects/:id" element={
            <AuthGuard>
              <ProjectDetailPage />
            </AuthGuard>
          } />

          <Route path="/projects/:id/dashboard" element={
            <AuthGuard>
              <DashboardPage />
            </AuthGuard>
          } />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}

function ProjectListContainer() {
  const navigate = useNavigate()
  return <ProjectListPage
    onNewProjectClick={() => navigate('/new')}
    onProjectClick={(id) => navigate(`/projects/${id}`)}
  />
}

export default App
