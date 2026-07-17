import { NextRequest, NextResponse } from 'next/server'

function backendOrigin(): string {
  try {
    return new URL(process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000').origin
  } catch {
    return 'http://127.0.0.1:8000'
  }
}

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString('base64')
  const development = process.env.NODE_ENV !== 'production'
  const scriptSources = ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"]
  const connectSources = ["'self'", backendOrigin()]
  if (development) {
    scriptSources.push("'unsafe-eval'")
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
    "style-src 'self' 'unsafe-inline'",
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
