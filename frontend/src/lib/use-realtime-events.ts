'use client'

import { useEffect, useRef, useState } from 'react'
import { ADMIN_TENANT_CONTEXT_ID_KEY } from './admin-tenant-context'
import { API_URL, authApi } from './api'
import { getAccessToken, setAccessToken } from './auth-token'

export type RealtimeEvent = {
  type: 'message.created' | 'conversation.created' | 'conversation.updated' | string
  conversation_id?: string
  message_id?: string
  sender?: string
  status?: string
}

export function useRealtimeEvents(onEvent: (event: RealtimeEvent) => void) {
  const callbackRef = useRef(onEvent)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    callbackRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    let stopped = false
    let controller: AbortController | null = null
    let retryTimer: number | null = null
    let retryMs = 1000

    const connect = async () => {
      if (stopped) return
      let token = getAccessToken()
      if (!token) {
        try {
          token = await authApi.refreshWithCookie()
          setAccessToken(token)
        } catch {
          retryTimer = window.setTimeout(connect, retryMs)
          retryMs = Math.min(retryMs * 2, 15000)
          return
        }
      }
      controller = new AbortController()
      const headers: Record<string, string> = {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      }
      const tenantContextId = window.localStorage.getItem(ADMIN_TENANT_CONTEXT_ID_KEY)
      if (tenantContextId) headers['X-Tenant-ID'] = tenantContextId

      try {
        const response = await fetch(`${API_URL}/realtime/events`, {
          credentials: 'include',
          headers,
          signal: controller.signal,
        })
        if (response.status === 401) {
          const refreshed = await authApi.refreshWithCookie()
          setAccessToken(refreshed)
          throw new Error('token-refreshed')
        }
        if (!response.ok || !response.body) throw new Error(`stream-${response.status}`)
        setConnected(true)
        retryMs = 1000
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (!stopped) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
          const frames = buffer.split('\n\n')
          buffer = frames.pop() || ''
          frames.forEach((frame) => {
            const data = frame
              .split('\n')
              .filter((line) => line.startsWith('data:'))
              .map((line) => line.slice(5).trim())
              .join('\n')
            if (!data) return
            try {
              callbackRef.current(JSON.parse(data) as RealtimeEvent)
            } catch {
              // Ignore malformed third-party proxy frames.
            }
          })
        }
      } catch (error) {
        if (!stopped && (error as Error).name !== 'AbortError') {
          setConnected(false)
        }
      } finally {
        setConnected(false)
        if (!stopped) {
          retryTimer = window.setTimeout(connect, retryMs)
          retryMs = Math.min(retryMs * 2, 15000)
        }
      }
    }

    void connect()
    return () => {
      stopped = true
      controller?.abort()
      if (retryTimer !== null) window.clearTimeout(retryTimer)
    }
  }, [])

  return { connected }
}
