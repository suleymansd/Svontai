import { NextRequest, NextResponse } from 'next/server'

function backendOrigin(): string {
  try {
    return new URL(process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000').origin
  } catch {
    return 'http://127.0.0.1:8000'
  }
}

function sentryOrigin(): string | null {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN
  if (!dsn) return null
  try {
    return new URL(dsn).origin
  } catch {
    return null
  }
}

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString('base64')
  const development = process.env.NODE_ENV !== 'production'
  const scriptSources = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"]
  const styleSources = development
    ? ["'self'", "'unsafe-inline'"]
    : ["'self'", `'nonce-${nonce}'`]
  const connectSources = ["'self'", backendOrigin()]
  const monitoringOrigin = sentryOrigin()
  if (monitoringOrigin) connectSources.push(monitoringOrigin)
  if (development) {
    scriptSources.push("'unsafe-eval'")
    // Turbopack injects nonce-less style elements for HMR. Production remains
    // nonce-only and is covered by the production build/smoke gate.
    connectSources.push('http:', 'https:', 'ws:', 'wss:')
  }

  const csp = [
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `style-src ${styleSources.join(' ')}`,
    `style-src-elem ${styleSources.join(' ')}`,
    // React dynamic style attributes remain narrowly allowed; executable style
    // blocks and injected <style> elements require the per-request nonce.
    "style-src-attr 'unsafe-inline'",
    `script-src ${scriptSources.join(' ')}`,
    `connect-src ${connectSources.join(' ')}`,
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    ...(development ? [] : ['upgrade-insecure-requests']),
  ].join('; ')

  const requestHeaders = new Headers(request.headers)
  requestHeaders.set('x-nonce', nonce)
  requestHeaders.set('Content-Security-Policy', csp)

  const response = NextResponse.next({ request: { headers: requestHeaders } })
  response.headers.set('Content-Security-Policy', csp)
  return response
}

export const config = {
  matcher: [
    {
      source: '/((?!api|_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
      missing: [
        { type: 'header', key: 'next-router-prefetch' },
        { type: 'header', key: 'purpose', value: 'prefetch' },
      ],
    },
  ],
}
