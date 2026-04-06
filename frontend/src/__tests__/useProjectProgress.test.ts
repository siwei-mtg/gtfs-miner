import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useProjectProgress } from '../hooks/useProjectProgress'
import type { WebSocketMessage } from '../types/api'

// Minimal WebSocket mock
type WsEventType = 'open' | 'message' | 'close'

class MockWebSocket {
  static instances: MockWebSocket[] = []

  url: string
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  trigger(event: WsEventType, data?: string) {
    if (event === 'open') this.onopen?.()
    if (event === 'message') this.onmessage?.({ data: data! })
    if (event === 'close') this.onclose?.()
  }

  close() {
    this.onclose?.()
  }
}

beforeEach(() => {
  MockWebSocket.instances = []
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const makeMsg = (step: string, status: WebSocketMessage['status'] = 'processing'): WebSocketMessage => ({
  project_id: 'proj-1',
  status,
  step,
  time_elapsed: 1.0,
  error: null,
})

describe('useProjectProgress', () => {
  it('does not connect when projectId is null', () => {
    renderHook(() => useProjectProgress(null))
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('connects to the correct WebSocket URL', () => {
    renderHook(() => useProjectProgress('proj-1'))
    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.instances[0].url).toBe('/api/v1/projects/proj-1/ws')
  })

  it('sets isConnected true on open, false on close', () => {
    const { result } = renderHook(() => useProjectProgress('proj-1'))
    const ws = MockWebSocket.instances[0]

    expect(result.current.isConnected).toBe(false)

    act(() => ws.trigger('open'))
    expect(result.current.isConnected).toBe(true)

    act(() => ws.trigger('close'))
    expect(result.current.isConnected).toBe(false)
  })

  it('appends messages and updates latestStatus on each message event', () => {
    const { result } = renderHook(() => useProjectProgress('proj-1'))
    const ws = MockWebSocket.instances[0]

    act(() => ws.trigger('open'))
    act(() => ws.trigger('message', JSON.stringify(makeMsg('step_1'))))
    act(() => ws.trigger('message', JSON.stringify(makeMsg('step_2', 'completed'))))

    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0].step).toBe('step_1')
    expect(result.current.messages[1].step).toBe('step_2')
    expect(result.current.latestStatus).toBe('completed')
  })

  it('closes WebSocket on unmount', () => {
    const { unmount } = renderHook(() => useProjectProgress('proj-1'))
    const ws = MockWebSocket.instances[0]
    const closeSpy = vi.spyOn(ws, 'close')

    unmount()
    expect(closeSpy).toHaveBeenCalled()
  })

  it('reconnects when projectId changes', () => {
    const { rerender } = renderHook(
      ({ id }: { id: string | null }) => useProjectProgress(id),
      { initialProps: { id: 'proj-1' } }
    )
    expect(MockWebSocket.instances).toHaveLength(1)

    act(() => rerender({ id: 'proj-2' }))
    expect(MockWebSocket.instances).toHaveLength(2)
    expect(MockWebSocket.instances[1].url).toBe('/api/v1/projects/proj-2/ws')
  })
})
