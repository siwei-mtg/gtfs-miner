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
    render(<ProgressPanel messages={[makeMsg('[1/9] 读取与解压 GTFS 文件')]} />)
    expect(screen.getAllByRole('listitem')).toHaveLength(9)
  })

  it('recognises [8/9] persist-to-DB step and shows its label', () => {
    const step = '[8/9] 将结果写入数据库'
    render(<ProgressPanel messages={[makeMsg(step)]} />)
    expect(screen.getByText(step)).toBeInTheDocument()
  })

  it('keeps progressPercentage below 100% while status is processing, even if all steps received', () => {
    const allSteps = [
      '[1/9] 读取与解压 GTFS 文件',
      '[2/9] 标准化 GTFS 表',
      '[3/9] 空间聚类生成站点映射',
      '[4/9] 生成行程、弧段与班次数据',
      '[5/9] 生成线路与子线路',
      '[6/9] 生成服务日期与日类型',
      '[7/9] 计算通过次数与 KCC 指标',
      '[8/9] 将结果写入数据库',
      '[9/9] 构建查询数据库（DWD）',
    ].map((s) => makeMsg(s, 'processing'))
    render(<ProgressPanel messages={allSteps} status="processing" />)
    // The percentage label sits beside the "Progression" caption — assert it never reads 100%.
    expect(screen.getByText('99%')).toBeInTheDocument()
    expect(screen.queryByText('100%')).not.toBeInTheDocument()
  })

  it('reaches 100% only when status flips to completed', () => {
    const msgs = [
      makeMsg('[9/9] 构建查询数据库（DWD）', 'processing'),
      makeMsg('处理完成（总耗时 12 秒）', 'completed', 12.0),
    ]
    render(<ProgressPanel messages={msgs} status="completed" />)
    expect(screen.getByText('100%')).toBeInTheDocument()
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

  it('test_progress_panel_completed_step_checkmark', () => {
    // 完成步骤含 ✓ 文本
    const msgs = [
      makeMsg('[1/7] 读取与解压 GTFS 文件', 'processing', 1.0)
    ]
    render(<ProgressPanel messages={msgs} />)
    expect(screen.getByText('✓')).toBeInTheDocument()
  })
})
