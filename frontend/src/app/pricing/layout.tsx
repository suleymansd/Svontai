import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Pricing',
  description: 'SvontAI planları: Starter, Growth ve Enterprise. Kurumsal otomasyon için esnek fiyatlandırma.',
}

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
