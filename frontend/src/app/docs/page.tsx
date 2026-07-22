import type { Metadata } from 'next'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { CustomerGuide } from '@/components/docs/customer-guide'

export const metadata: Metadata = {
  title: 'Kullanım Kılavuzu | SvontAI',
  description: 'SvontAI kurulum, WhatsApp bağlantısı, AI asistan, medya, randevu, arama ve raporlama kullanım kılavuzu.',
  alternates: { canonical: '/docs' },
}

export default function DocsPage() {
  return (
    <MarketingShell>
      <CustomerGuide />
    </MarketingShell>
  )
}
