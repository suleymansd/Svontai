import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Pricing',
  description: 'SvontAI planları: Free, Pro, Premium ve Kurumsal. Tool run limitleri ve yükseltme akışları ile üretim hazır fiyatlandırma.',
}

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
