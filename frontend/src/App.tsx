import { useState } from 'react'
import { UploadForm } from './components/UploadForm'
import { ProgressPanel } from './components/ProgressPanel'
import { DownloadButton } from './components/DownloadButton'
import { useProjectProgress } from './hooks/useProjectProgress'
import { createProject, uploadGtfs } from './api/client'
import type { ProjectCreate } from './types/api'
import './App.css'

type AppPhase = 'idle' | 'uploading' | 'active'

function App() {
  const [phase, setPhase] = useState<AppPhase>('idle')
  const [projectId, setProjectId] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { messages, latestStatus } = useProjectProgress(
    phase === 'active' ? projectId : null
  )

  async function handleSubmit(file: File, params: ProjectCreate) {
    setUploadError(null)
    setPhase('uploading')
    try {
      const project = await createProject(params)
      await uploadGtfs(project.id, file)
      setProjectId(project.id)
      setPhase('active')
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Erreur inattendue')
      setPhase('idle')
    }
  }

  const isCompleted = latestStatus === 'completed'
  const isFailed = latestStatus === 'failed'

  return (
    <main>
      <h1>GTFS Miner</h1>

      {phase === 'idle' || phase === 'uploading' ? (
        <UploadForm
          onSubmit={handleSubmit}
          isLoading={phase === 'uploading'}
          error={uploadError}
        />
      ) : (
        <>
          <ProgressPanel messages={messages} />
          <DownloadButton
            projectId={isCompleted ? projectId : null}
            disabled={!isCompleted}
          />
          {(isCompleted || isFailed) && (
            <button
              onClick={() => {
                setPhase('idle')
                setProjectId(null)
                setUploadError(null)
              }}
            >
              Nouveau traitement
            </button>
          )}
        </>
      )}
    </main>
  )
}

export default App
