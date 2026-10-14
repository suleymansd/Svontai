/** @type {import('next').NextConfig} */
const securityHeaders = [
  {
    key: 'X-DNS-Prefetch-Control',
    value: 'on',
  },
  {
    key: 'X-Frame-Options',
    value: 'DENY',
  },
  {
    key: 'X-Content-Type-Options',
    value: 'nosniff',
  },
  {
    key: 'Referrer-Policy',
    value: 'strict-origin-when-cross-origin',
  },
  {
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(), geolocation=(), payment=()',
  },
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=63072000; includeSubDomains; preload',
  },
]

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: '/:path*',
        headers: securityHeaders,
      },
    ]
  },
}

module.exports = (phase) => {
  if (phase === require('next/constants').PHASE_PRODUCTION_BUILD) {
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL?.trim()
    if (!backend) throw new Error('NEXT_PUBLIC_BACKEND_URL must be set before building the frontend.')
    const url = new URL(backend)
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) {
      throw new Error('NEXT_PUBLIC_BACKEND_URL must be an HTTP(S) URL without credentials.')
    }
  }
  return nextConfig
}
