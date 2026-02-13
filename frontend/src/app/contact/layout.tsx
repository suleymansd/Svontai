import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Contact',
  description: 'SvontAI demo, fiyat ve güvenlik talepleri için satış ekibimizle iletişime geçin.',
}

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return children
}
