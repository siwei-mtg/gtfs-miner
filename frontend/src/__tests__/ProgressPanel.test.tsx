import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProgressPanel } from '@/components/organisms/ProgressPanel'
import type { WebSocketMessage } from '../types/api'

function makeMsg(step: string, status: WebSocketMessage['status'] = 'processing', elapsed = 1.5): WebSocketMessage {
  return { project_id: 'p1', status, step, time_elapsed: elapsed, error: null }
}

describe('ProgressPanel', () => {
  it('shows waiting message when messages is empty', () => {
    render(<ProgressPanel messages={[]} />)
    expect(screen.getByText(/en attente/i)).toBeInTheDocument()
  })

  it('renders 9 step slots', () => {
    render(<ProgressPanel messages={[makeMsg('[1/9] Lecture et décompression du fichier GTFS')]} />)
    expect(screen.getAllByRole('listitem')).toHaveLength(9)
  })

  it('recognises [8/9] persist-to-DB step and shows its label', () => {
    const step = '[8/9] Écriture des résultats en base de données'
    render(<ProgressPanel messages={[makeMsg(step)]} />)
    expect(screen.getByText(step)).toBeInTheDocument()
  })

  it('keeps progressPercentage below 100% while status is processing, even if all steps received', () => {
    const allSteps = [
      '[1/9] Lecture et décompression du fichier GTFS',
      '[2/9] Normalisation des tables GTFS',
      '[3/9] Clustering spatial et cartographie des arrêts',
      '[4/9] Génération des itinéraires, arcs et courses',
      '[5/9] Génération des lignes et sous-lignes',
      '[6/9] Génération des dates de service et types de jour',
      '[7/9] Calcul des nombres de passages et indicateurs KCC',
      '[8/9] Écriture des résultats en base de données',
      '[9/9] Construction de la base de requêtes (DWD)',
    ].map((s) => makeMsg(s, 'processing'))
    render(<ProgressPanel messages={allSteps} status="processing" />)
    // The percentage label sits beside the "Progression" caption — assert it never reads 100%.
    expect(screen.getByText('99%')).toBeInTheDocument()
    expect(screen.queryByText('100%')).not.toBeInTheDocument()
  })

  it('reaches 100% only when status flips to completed', () => {
    const msgs = [
      makeMsg('[9/9] Construction de la base de requêtes (DWD)', 'processing'),
      makeMsg('Traitement terminé (durée totale : 12 s)', 'completed', 12.0),
    ]
    render(<ProgressPanel messages={msgs} status="completed" />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('displays the full step text from messages', () => {
    const step = '[2/7] Normalisation des tables GTFS (chargées : stop_times)'
    render(<ProgressPanel messages={[makeMsg('[1/7] Lecture et décompression du fichier GTFS'), makeMsg(step)]} />)
    expect(screen.getByText(step)).toBeInTheDocument()
  })

  it('shows elapsed time from the latest message', () => {
    render(<ProgressPanel messages={[makeMsg('[1/7] Lecture et décompression du fichier GTFS', 'processing', 4.2)]} />)
    expect(screen.getByLabelText('elapsed-time')).toHaveTextContent('4.2')
  })

  it('shows completed status', () => {
    const msgs = [
      makeMsg('[7/7] Calcul des nombres de passages et indicateurs KCC (done)', 'completed', 30.0),
    ]
    render(<ProgressPanel messages={msgs} />)
    expect(screen.getByLabelText('status')).toHaveTextContent('Terminé')
  })

  it('shows failed status with error message', () => {
    const msg: WebSocketMessage = {
      project_id: 'p1',
      status: 'failed',
      step: 'Traitement échoué',
      time_elapsed: 5.0,
      error: 'FileNotFoundError',
    }
    render(<ProgressPanel messages={[msg]} />)
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('FileNotFoundError')
  })

  it('shows processing status during intermediate step', () => {
    render(<ProgressPanel messages={[makeMsg('[3/7] Clustering spatial et cartographie des arrêts (100 arrêts)')]} />)
    expect(screen.getByLabelText('status')).toHaveTextContent('En cours')
  })

  it('test_progress_panel_completed_step_checkmark', () => {
    // L'étape terminée contient le texte ✓
    const msgs = [
      makeMsg('[1/7] Lecture et décompression du fichier GTFS', 'processing', 1.0)
    ]
    render(<ProgressPanel messages={msgs} />)
    expect(screen.getByText('✓')).toBeInTheDocument()
  })
})
