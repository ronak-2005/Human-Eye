'use client'

import { useEffect, useRef, useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { WSEvent, VerificationListItem } from '../lib/types'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export function useWebSocket() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [latestEvent, setLatestEvent] = useState<VerificationListItem | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const qc = useQueryClient()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    const ws = new WebSocket(`${WS_URL}/api/v1/ws/verifications`)
    wsRef.current = ws

    ws.onopen = () => setStatus('connected')

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data)
        if (event.type === 'verification.complete') {
          setLatestEvent(event.data)
          // Invalidate the verification list cache so table refreshes
          qc.invalidateQueries({ queryKey: ['verifications'] })
          qc.invalidateQueries({ queryKey: ['stats', 'dashboard'] })
        }
      } catch {
        // malformed message — ignore
      }
    }

    ws.onerror = () => setStatus('error')

    ws.onclose = () => {
      setStatus('disconnected')
      // Reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000)
    }
  }, [qc])

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current)
    wsRef.current?.close()
    wsRef.current = null
    setStatus('disconnected')
  }, [])

  useEffect(() => {
    connect()
    return disconnect
  }, [connect, disconnect])

  return { status, latestEvent }
}
