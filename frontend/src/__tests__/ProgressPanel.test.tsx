import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProgressPanel } from '../components/ProgressPanel'
import type { WebSocketMessage } from '../types/api'

function makeMsg(step: string, status: WebSocketMessage['status'] = 'processing', elapsed = 1.5): WebSocketMessage {
  return { project_id: 'p1', status, step, time_elapsed: elapsed, error: null }
}

describe('ProgressPanel', () => {
  it('shows waiting message when messages is empty', () => {
    render(<ProgressPanel messages={[]} />)
    expect(screen.getByText(/en attente/i)).toBeInTheDocument()
  })

  it('renders 7 step slots', () => {
    render(<ProgressPanel messages={[makeMsg('[1/7] 读取与解压 GTFS 文件')]} />)
    expect(screen.getAllByRole('listitem')).toHaveLength(7)
  })

  it('displays the full step text from messages', () => {
    const step = '[2/7] 标准化 GTFS 表（已加载：stop_times）'
    render(<ProgressPanel messages={[makeMsg('[1/7] 读取与解压 GTFS 文件'), makeMsg(step)]} />)
    expect(screen.getByText(step)).toBeInTheDocument()
  })

  it('shows elapsed time from the latest message', () => {
    render(<ProgressPanel messages={[makeMsg('[1/7] 读取与解压 GTFS 文件', 'processing', 4.2)]} />)
    expect(screen.getByLabelText('elapsed-time')).toHaveTextContent('4.2')
  })

  it('shows completed status', () => {
    const msgs = [
      makeMsg('[7/7] 计算通过次数与 KCC 指标（done）', 'completed', 30.0),
    ]
    render(<ProgressPanel messages={msgs} />)
    expect(screen.getByLabelText('status')).toHaveTextContent('Terminé')
  })

  it('shows failed status with error message', () => {
    const msg: WebSocketMessage = {
      project_id: 'p1',
      status: 'failed',
      step: '处理失败',
      time_elapsed: 5.0,
      error: 'FileNotFoundError',
    }
    render(<ProgressPanel messages={[msg]} />)
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('FileNotFoundError')
  })

  it('shows processing status during intermediate step', () => {
    render(<ProgressPanel messages={[makeMsg('[3/7] 空间聚类生成站点映射（100 停靠站）')]} />)
    expect(screen.getByLabelText('status')).toHaveTextContent('En cours')
  })
})
