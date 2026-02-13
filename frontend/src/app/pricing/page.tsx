'use client'
import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Check, Star } from 'lucide-react'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'

const plans = [
  {
    name: 'Free',
    key: 'free',
    description: 'Temel otomasyonlar için',
    monthly: 0,
    yearly: 0,
    highlights: ['1 bot', '100 mesaj', 'Temel raporlar'],
  },
  {
    name: 'Starter',
    key: 'starter',
    description: 'Yeni büyüyen ekipler',
    monthly: 299,
    yearly: 2990,
    highlights: ['2 bot', '1.000 mesaj', 'Analytics', 'Otomasyon kataloğu'],
  },
  {
    name: 'Growth',
    key: 'growth',
    description: 'Operasyon ekipleri için',
    monthly: 799,
    yearly: 7990,
    highlights: ['5 bot', '5.000 mesaj', 'Error Center', 'SLA yönetimi'],
  },
  {
    name: 'Enterprise',
    key: 'enterprise',
    description: 'Kurumsal ölçekte',
    monthly: null,
    yearly: null,
    highlights: ['Sınırsız bot', 'Özel SLA', 'Dedicated support', 'SSO + Audit'],
  },
]

export default function PricingPage() {
  const [billing, setBilling] = useState<'monthly' | 'yearly'>('monthly')

  const pricedPlans = useMemo(() => {
    return plans.map((plan) => {
      if (plan.monthly === null) return plan
      return {
        ...plan,
        price: billing === 'monthly' ? plan.monthly : plan.yearly,
      }
    })
  }, [billing])

  return (
    <MarketingShell>
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <Reveal className="space-y-6">
          <Badge variant="outline">Fiyatlandırma</Badge>
          <h1 className="text-4xl font-semibold">Her ölçek için hazır planlar</h1>
          <p className="text-muted-foreground">Tüm planlarda multi-tenant izolasyon, audit log ve güvenlik standarttır.</p>
          <div className="flex items-center gap-3">
            <Button variant={billing === 'monthly' ? 'default' : 'outline'} onClick={() => setBilling('monthly')}>
              Aylık
            </Button>
            <Button variant={billing === 'yearly' ? 'default' : 'outline'} onClick={() => setBilling('yearly')}>
              Yıllık (2 ay hediye)
            </Button>
          </div>
        </Reveal>

        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {pricedPlans.map((plan, index) => (
            <Reveal key={plan.key} delay={index * 80}>
              <Card className="h-full border-border/60">
                <CardContent className="p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold">{plan.name}</h3>
                    {plan.key === 'growth' && <Badge>Popüler</Badge>}
                  </div>
                  <div className="text-3xl font-semibold">
                    {plan.monthly === null ? 'Özel teklif' : `₺${plan.price}`}
                    {plan.monthly !== null && <span className="text-sm text-muted-foreground">/{billing === 'monthly' ? 'ay' : 'yıl'}</span>}
                  </div>
                  <p className="text-sm text-muted-foreground">{plan.description}</p>
                  <div className="space-y-2 text-sm">
                    {plan.highlights.map((item) => (
                      <div key={item} className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-success" />
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                  <Link href="/contact" className="block">
                    <Button className="w-full" variant={plan.key === 'growth' ? 'default' : 'outline'}>
                      {plan.monthly === null ? 'Teklif Al' : 'Planı Seç'}
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            </Reveal>
          ))}
        </div>

        <div className="mt-16 rounded-3xl border border-border/60 bg-card/60 p-8 text-center">
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Star className="h-4 w-4 text-warning" />
            SvontAI Enterprise ile SLA ve güvenlik özel gereksinimlerinizi karşılıyoruz.
          </div>
        </div>
      </section>
    </MarketingShell>
  )
}
