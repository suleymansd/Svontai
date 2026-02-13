import type { Metadata } from 'next'
import { Sora } from 'next/font/google'
import './globals.css'
import { Providers } from '@/components/providers'

const sora = Sora({ 
  subsets: ['latin'],
  variable: '--font-sans',
})

const metadataBase = new URL(process.env.NEXT_PUBLIC_SITE_URL || 'https://svontai.com')

export const metadata: Metadata = {
  metadataBase,
  title: {
    default: 'SvontAI — Automation OS for WhatsApp-first teams',
    template: '%s — SvontAI',
  },
  description: 'SvontAI, WhatsApp müşteri desteğini otomasyonlarla ölçekleyen kurumsal operasyon platformudur.',
  icons: {
    icon: '/logo.png',
  },
  openGraph: {
    title: 'SvontAI — Automation OS for WhatsApp-first teams',
    description: 'SvontAI, WhatsApp müşteri desteğini otomasyonlarla ölçekleyen kurumsal operasyon platformudur.',
    url: metadataBase,
    siteName: 'SvontAI',
    locale: 'tr_TR',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'SvontAI — Automation OS for WhatsApp-first teams',
    description: 'SvontAI, WhatsApp müşteri desteğini otomasyonlarla ölçekleyen kurumsal operasyon platformudur.',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body className={`${sora.variable} font-sans antialiased`}>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
