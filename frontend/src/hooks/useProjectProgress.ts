import { useEffect, useRef, useState } from 'react'
import { getProject } from '../api/client'
import type { ProjectStatus, WebSocketMessage } from '../types/api'

interface UseProjectProgressResult {
  messages: WebSocketMessage[]
  latestStatus: ProjectStatus | null
  isConnected: boolean
}

export function useProjectProgress(projectId: string | null): UseProjectProgressResult {
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  const [latestStatus, setLatestStatus] = useState<ProjectStatus | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!projectId) return

    setMessages([])
    setLatestStatus(null)
    setIsConnected(false)

    // Seed initial status immediately (HTTP) so completed projects are usable
    // even before the WebSocket connects or when it is unavailable.
    getProject(projectId)
      .then((p) => setLatestStatus(p.status as ProjectStatus))
      .catch(() => { /* ignore — WebSocket will provide live updates */ })

    // setTimeout(0) prevents React 18 StrictMode from opening two WebSocket
    // connections simultaneously (fake-unmount closes the first one immediately,
    // producing "connection interrupted" console errors). The clearTimeout in
    // the cleanup cancels the pending connection before it is established.
    let mounted = true
    const timerId = setTimeout(() => {
      if (!mounted) return

      const apiOrigin = (import.meta.env.VITE_API_URL as string | undefined) ?? ''
      const wsOrigin = apiOrigin.replace(/^https/, 'wss').replace(/^http/, 'ws')
      const ws = new WebSocket(`${wsOrigin}/api/v1/projects/${projectId}/ws`)
      wsRef.current = ws

      ws.onopen = () => { if (mounted) setIsConnected(true) }

      ws.onmessage = (event: MessageEvent) => {
        if (!mounted) return
        const msg: WebSocketMessage = JSON.parse(event.data as string)
        setMessages((prev) => [...prev, msg])
        // Prevent regression: once the project is in a terminal state
        // (completed / failed), WebSocket history replay of intermediate
        // steps must not overwrite it with a non-terminal status.
        setLatestStatus((prev) => {
          if (prev === 'completed' || prev === 'failed') return prev
          return msg.status
        })
      }

      ws.onclose = () => { if (mounted) setIsConnected(false) }
    }, 0)

    return () => {
      mounted = false
      clearTimeout(timerId)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [projectId])

  return { messages, latestStatus, isConnected }
}
