import { ADMIN_TENANT_CONTEXT_ID_KEY } from './admin-tenant-context'
import { normalizeApiUrl } from './api-url'
import { getAccessToken } from './auth-token'

type ProductEventCategory = 'navigation' | 'action' | 'error' | 'funnel' | 'performance'

type ProductEvent = {
  name: string
  category: ProductEventCategory
  path?: string
  session_id: string
  properties: Record<string, string | number | boolean | null>
  occurred_at: string
}

const API_URL = normalizeApiUrl(process.env.NEXT_PUBLIC_BACKEND_URL)
const SESSION_KEY = 'svontai_product_session'
const BLOCKED_KEY_PARTS = ['content', 'email', 'message', 'name', 'password', 'phone', 'prompt', 'query', 'secret', 'text', 'token']
const ALLOWED_PROPERTY_KEYS = new Set([
  'action', 'count', 'duration_ms', 'method', 'mode', 'provider', 'result', 'route', 'status', 'step', 'turn',
])
const SAFE_PROPERTY_VALUE = /^[A-Za-z0-9_./:-]{1,200}$/
let queue: ProductEvent[] = []
let flushTimer: number | null = null
let flushing = false

function sessionId(): string {
  if (typeof window === 'undefined') return 'server-session'
  const current = window.sessionStorage.getItem(SESSION_KEY)
  if (current) return current
  const generated = (window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`).replace(/[^A-Za-z0-9_-]/g, '')
  window.sessionStorage.setItem(SESSION_KEY, generated)
  return generated
}

function safeProperties(properties: Record<string, unknown> = {}) {
  const safe: Record<string, string | number | boolean | null> = {}
  Object.entries(properties).forEach(([rawKey, rawValue]) => {
    const key = rawKey.toLowerCase().slice(0, 50)
    if (!key || !ALLOWED_PROPERTY_KEYS.has(key) || BLOCKED_KEY_PARTS.some((part) => key.includes(part))) return
    if (rawValue === null || typeof rawValue === 'boolean' || typeof rawValue === 'number') {
      safe[key] = rawValue
    } else if (typeof rawValue === 'string' && SAFE_PROPERTY_VALUE.test(rawValue)) {
      safe[key] = key === 'route' ? (safePath(rawValue) || '/') : rawValue
    }
  })
  return safe
}

function safePath(path?: string) {
  if (!path || typeof window === 'undefined') return path
  try {
    return new URL(path, window.location.origin).pathname
  } catch {
    return path.split('?')[0].slice(0, 300)
  }
}

async function flush() {
  if (flushing || queue.length === 0 || typeof window === 'undefined') return
  const token = getAccessToken()
  if (!token) {
    queue = []
    return
  }
  flushing = true
  const events = queue.splice(0, 20)
  try {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    }
    const tenantContextId = window.localStorage.getItem(ADMIN_TENANT_CONTEXT_ID_KEY)
    if (tenantContextId) headers['X-Tenant-ID'] = tenantContextId
    const response = await fetch(`${API_URL}/product-analytics/events`, {
      method: 'POST',
      credentials: 'include',
      keepalive: true,
      headers,
      body: JSON.stringify({ events }),
    })
    if (!response.ok && response.status !== 401 && response.status !== 403) {
      queue = [...events, ...queue].slice(0, 100)
    }
  } catch {
    queue = [...events, ...queue].slice(0, 100)
  } finally {
    flushing = false
    if (queue.length > 0) scheduleFlush()
  }
}

function scheduleFlush() {
  if (typeof window === 'undefined' || flushTimer !== null) return
  flushTimer = window.setTimeout(() => {
    flushTimer = null
    void flush()
  }, 1500)
}

export function trackProductEvent(
  name: string,
  properties: Record<string, unknown> = {},
  category: ProductEventCategory = 'action',
  path?: string,
) {
  if (typeof window === 'undefined' || name === 'product_events') return
  queue.push({
    name: name.toLowerCase().replace(/[^a-z0-9_.-]/g, '_').slice(0, 80),
    category,
    path: safePath(path || window.location.pathname),
    session_id: sessionId(),
    properties: safeProperties(properties),
    occurred_at: new Date().toISOString(),
  })
  queue = queue.slice(-100)
  scheduleFlush()
}

export function normalizeTrackedApiPath(url: string) {
  return safePath(url.replace(API_URL, '')) || '/'
}
