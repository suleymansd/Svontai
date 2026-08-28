export type PublicPaidPlan = {
  code: 'pro' | 'premium' | 'enterprise'
  name: string
  description: string
  monthlyPrice: number
  yearlyPrice: number
  setupFee: number | null
  features: string[]
  popular: boolean
  cta: string
}

export const PUBLIC_PAID_PLANS: PublicPaidPlan[] = [
  {
    code: 'pro',
    name: 'Başlangıç',
    description: 'Küçük işletmeler için',
    monthlyPrice: 999,
    yearlyPrice: 9_990,
    setupFee: 2_499,
    features: [
      '2 AI asistan',
      '1.000 AI yanıtı/ay',
      '1 WhatsApp bağlantısı',
      'Web widget',
      'E-posta desteği',
      'Temel analizler',
    ],
    popular: false,
    cta: 'Kurulumu Başlat',
  },
  {
    code: 'premium',
    name: 'Profesyonel',
    description: 'Büyüyen işletmeler için',
    monthlyPrice: 4_999,
    yearlyPrice: 49_990,
    setupFee: 9_999,
    features: [
      '5 AI asistan',
      '10.000 AI yanıtı/ay',
      'WhatsApp ve randevu otomasyonu',
      'Öncelikli destek',
      'Gelişmiş analizler',
      'API erişimi',
    ],
    popular: true,
    cta: 'Profesyonel Kurulum',
  },
  {
    code: 'enterprise',
    name: 'Kurumsal',
    description: 'Ajanslar ve yüksek hacimli operasyonlar için',
    monthlyPrice: 14_999,
    yearlyPrice: 149_990,
    setupFee: null,
    features: [
      '20 AI asistan',
      '50.000 AI yanıtı/ay',
      'Limit üzeri özel fiyatlandırma',
      'Çoklu müşteri yönetimi',
      'Özel entegrasyonlar',
      'Özel SLA ve destek seçeneği',
    ],
    popular: false,
    cta: 'Teklif Al',
  },
]

export function formatTry(amount: number): string {
  return `₺${amount.toLocaleString('tr-TR')}`
}
