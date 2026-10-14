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
          if (stopped) return
          retryTimer = window.setTimeout(connect, retryMs)
          retryMs = Math.min(retryMs * 2, 15000)
          return
        }
      }
      if (stopped) return
      controller = new AbortController()
      const active = controller
      let watchdog: number | undefined
      const resetWatchdog = () => {
        window.clearTimeout(watchdog)
        watchdog = window.setTimeout(() => active.abort(), 40_000)
      }
      const headers: Record<string, string> = {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
      }
      const tenantContextId = window.localStorage.getItem(ADMIN_TENANT_CONTEXT_ID_KEY)
      if (tenantContextId) headers['X-Tenant-ID'] = tenantContextId

      try {
        resetWatchdog()
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
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (!stopped) {
          const { done, value } = await reader.read()
          if (done) break
          resetWatchdog()
          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
          const frames = buffer.split('\n\n')
          buffer = frames.pop() || ''
          if (buffer.length > 65_536) throw new Error('stream-buffer-limit')
          frames.forEach((frame) => {
            const data = frame
              .split('\n')
              .filter((line) => line.startsWith('data:'))
              .map((line) => line.slice(5).trim())
              .join('\n')
            if (!data) return
            try {
              const payload = JSON.parse(data)
              const eventName = frame.split('\n').find((line) => line.startsWith('event:'))?.slice(6).trim()
              const type = payload.type || (eventName === 'ready' ? 'ready' : undefined)
              if (type === 'ready') {
                setConnected(payload.live !== false)
                retryMs = 1000
              }
              if (typeof type === 'string') callbackRef.current({ ...payload, type } as RealtimeEvent)
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
        window.clearTimeout(watchdog)
        active.abort()
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
