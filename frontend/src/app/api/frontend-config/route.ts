import { NextResponse } from 'next/server'
import { normalizeApiUrl } from '@/lib/api-url'

export const dynamic = 'force-dynamic'

export async function GET() {
  const rawBackendUrl = process.env.NEXT_PUBLIC_BACKEND_URL

  try {
    const backendUrl = normalizeApiUrl(rawBackendUrl)
    return NextResponse.json({
      ok: true,
      backendUrl,
      backendUrlConfigured: true,
    })
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        backendUrl: null,
        backendUrlConfigured: false,
        error: error instanceof Error ? error.message : 'Invalid frontend backend URL configuration',
      },
      { status: 500 }
    )
  }
}
