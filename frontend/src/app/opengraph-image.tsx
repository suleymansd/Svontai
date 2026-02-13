import { ImageResponse } from 'next/og'

export const size = {
  width: 1200,
  height: 630,
}

export const contentType = 'image/png'

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: '100%',
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #0f172a 0%, #0a1f2e 40%, #0b3b40 100%)',
          color: 'white',
          fontFamily: 'sans-serif',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            alignItems: 'center',
          }}
        >
          <div
            style={{
              fontSize: 64,
              fontWeight: 700,
              letterSpacing: '-0.02em',
            }}
          >
            SvontAI
          </div>
          <div
            style={{
              fontSize: 28,
              opacity: 0.8,
              textAlign: 'center',
              maxWidth: 800,
            }}
          >
            Automation OS for WhatsApp-first support and operations
          </div>
        </div>
      </div>
    ),
    {
      ...size,
    }
  )
}
