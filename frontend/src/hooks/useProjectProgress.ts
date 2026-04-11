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

    // Seed initial status from DB so completed projects are immediately usable
    getProject(projectId)
      .then((p) => setLatestStatus(p.status as ProjectStatus))
      .catch(() => { /* ignore — WebSocket will provide live updates */ })

    const apiOrigin = (import.meta.env.VITE_API_URL as string | undefined) ?? ''
    const wsOrigin = apiOrigin.replace(/^https/, 'wss').replace(/^http/, 'ws')
    const ws = new WebSocket(`${wsOrigin}/api/v1/projects/${projectId}/ws`)
    wsRef.current = ws

    ws.onopen = () => setIsConnected(true)

    ws.onmessage = (event: MessageEvent) => {
      const msg: WebSocketMessage = JSON.parse(event.data as string)
      setMessages((prev) => [...prev, msg])
      setLatestStatus(msg.status)
    }

    ws.onclose = () => setIsConnected(false)

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [projectId])

  return { messages, latestStatus, isConnected }
}
