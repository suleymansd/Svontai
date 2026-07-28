import { NextRequest, NextResponse } from 'next/server'
import { normalizeApiUrl } from '@/lib/api-url'

export const dynamic = 'force-dynamic'

const ALLOWED_ACTIONS = new Set(['login', 'refresh', 'logout'])

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ action: string }> },
) {
  const { action } = await context.params
  if (!ALLOWED_ACTIONS.has(action)) {
    return NextResponse.json({ detail: 'Not found' }, { status: 404 })
  }

  const origin = (request.headers.get('origin') || '').replace(/\/+$/, '')
  const requestOrigin = request.nextUrl.origin.replace(/\/+$/, '')
  if (origin && origin !== requestOrigin) {
    return NextResponse.json({ detail: 'İstek kaynağına izin verilmiyor' }, { status: 403 })
  }

  const backendUrl = normalizeApiUrl(process.env.NEXT_PUBLIC_BACKEND_URL)
  const body = await request.text()
  const upstreamHeaders = new Headers({
    Accept: 'application/json',
    'Content-Type': request.headers.get('content-type') || 'application/json',
  })

  for (const header of ['authorization', 'cookie', 'origin', 'user-agent', 'x-request-id']) {
    const value = request.headers.get(header)
    if (value) upstreamHeaders.set(header, value)
  }

  try {
    const upstream = await fetch(`${backendUrl}/auth/${action}`, {
      method: 'POST',
      headers: upstreamHeaders,
      body: body || '{}',
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(15_000),
    })
    const response = new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: {
        'Cache-Control': 'no-store',
        'Content-Type': upstream.headers.get('content-type') || 'application/json',
      },
    })

    const setCookie = upstream.headers.get('set-cookie')
    if (setCookie) response.headers.set('set-cookie', setCookie)
    const requestId = upstream.headers.get('x-request-id')
    if (requestId) response.headers.set('x-request-id', requestId)
    return response
  } catch {
    return NextResponse.json(
      { detail: 'Kimlik doğrulama servisine ulaşılamadı' },
      { status: 503, headers: { 'Cache-Control': 'no-store' } },
    )
  }
}
