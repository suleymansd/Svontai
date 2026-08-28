import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Fiyatlandırma',
  description: 'SvontAI Başlangıç, Profesyonel ve Kurumsal paketlerinin güncel fiyatları, kullanım limitleri ve kurulum kapsamı.',
}

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
