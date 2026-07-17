'use client'
import { useMemo, useState } from 'react'
import Link from 'next/link'
import { Check, Star } from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'
import { billingApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'

const plans = [
  {
    name: 'Free',
    key: 'free',
    description: 'Ürünü tanımak ve demo akışı görmek için',
    monthly: 0,
    yearly: 0,
    highlights: ['Demo workspace', 'Otonom kurulum merkezi', 'Temel sağlık görünümü'],
  },
  {
    name: 'Pro',
    key: 'pro',
    description: 'Tek işletme için satışa hazır WhatsApp AI',
    monthly: 299,
    yearly: 2990,
    highlights: ['Done-for-you kurulum', '1 WhatsApp AI asistanı', 'Concierge bilgi formasyonu'],
  },
  {
    name: 'Premium',
    key: 'premium',
    description: 'Daha yoğun müşteri akışı ve entegrasyonlar',
    monthly: 599,
    yearly: 5990,
    highlights: ['Gelişmiş entegrasyonlar', 'Öncelikli destek', 'Incident ve retry otomasyonu'],
  },
  {
    name: 'Kurumsal',
    key: 'enterprise',
    description: 'Ajanslar ve çoklu müşteri operasyonları',
    monthly: null,
    yearly: null,
    highlights: ['Çoklu müşteri yönetimi', 'Launch board ve SLA', 'Özel güvenlik gereksinimleri', 'Dedicated support'],
  },
]

export default function PricingPage() {
  const [billing, setBilling] = useState<'monthly' | 'yearly'>('monthly')
  const [activeCheckoutPlan, setActiveCheckoutPlan] = useState<'pro' | 'premium' | null>(null)
  const { toast } = useToast()
  const { data: billingConfig } = useQuery<{
    mode: 'manual' | 'stripe'
    payments_enabled: boolean
    contact_url: string
  }>({
    queryKey: ['billing-config'],
    queryFn: () => billingApi.getConfig().then((response) => response.data),
  })

  const checkoutMutation = useMutation({
    mutationFn: async (input: { plan: 'pro' | 'premium'; interval: 'monthly' | 'yearly' }) => {
      const response = await billingApi.createStripeCheckoutSession(input)
      const checkoutUrl = response.data?.url
      if (!checkoutUrl) {
        throw new Error('Checkout URL alınamadı')
      }
      return checkoutUrl as string
    },
    onSuccess: (url) => {
      if (typeof window !== 'undefined') {
        window.location.href = url
      }
    },
    onError: (error: any) => {
      toast({
        title: 'Checkout başlatılamadı',
        description: getApiErrorMessage(error, 'Ödeme oturumu başlatılamadı.'),
        variant: 'destructive',
      })
    },
    onSettled: () => setActiveCheckoutPlan(null),
  })

  const pricedPlans = useMemo(() => {
    return plans.map((plan) => {
      if (plan.monthly === null) return plan
      return {
        ...plan,
        price: billing === 'monthly' ? plan.monthly : plan.yearly,
      }
    })
  }, [billing])

  const handleCheckout = (plan: 'pro' | 'premium') => {
    if (typeof window === 'undefined') return
    if (billingConfig?.mode !== 'stripe' || !billingConfig.payments_enabled) {
      const contactUrl = billingConfig?.contact_url || '/contact'
      window.location.href = `${contactUrl}?plan=${plan}&interval=${billing}`
      return
    }
    const token = localStorage.getItem('access_token')
    if (!token) {
      window.location.href = '/login?next=/pricing'
      return
    }
    setActiveCheckoutPlan(plan)
    checkoutMutation.mutate({ plan, interval: billing })
  }

  return (
    <MarketingShell>
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <Reveal className="space-y-6">
          <Badge variant="outline">Fiyatlandırma</Badge>
          <h1 className="text-4xl font-semibold">Kurulumu bizim üstlendiğimiz WhatsApp AI paketleri</h1>
          <p className="text-muted-foreground">
            Planlar; concierge bilgi formasyonu, otonom sağlık kontrolleri, audit log ve güvenli tenant izolasyonu üzerine kurulur.
          </p>
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
                    {plan.key === 'premium' && <Badge>Popüler</Badge>}
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
                  {plan.key === 'free' && (
                    <Link href="/register" className="block">
                      <Button className="w-full" variant="outline">
                        Demo Workspace Aç
                      </Button>
                    </Link>
                  )}
                  {(plan.key === 'pro' || plan.key === 'premium') && (
                    <Button
                      className="w-full"
                      variant={plan.key === 'premium' ? 'default' : 'outline'}
                      onClick={() => handleCheckout(plan.key as 'pro' | 'premium')}
                      disabled={checkoutMutation.isPending}
                    >
                      {checkoutMutation.isPending && activeCheckoutPlan === plan.key
                        ? 'Yönlendiriliyor...'
                        : billingConfig?.mode === 'stripe' && billingConfig.payments_enabled
                          ? 'Kurulumu Başlat'
                          : 'Görüşme Talebi Oluştur'}
                    </Button>
                  )}
                  {plan.key === 'enterprise' && (
                    <Link href="/contact?plan=enterprise">
                      <Button className="w-full" variant="outline">
                        Satışla İletişime Geç
                      </Button>
                    </Link>
                  )}
                </CardContent>
              </Card>
            </Reveal>
          ))}
        </div>

        <div className="mt-16 rounded-3xl border border-border/60 bg-card/60 p-8 text-center">
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Star className="h-4 w-4 text-warning" />
            Enterprise ve ajans planlarında launch board, çoklu müşteri yönetimi ve şirket içi bilgi formasyonu operasyonu birlikte gelir.
          </div>
        </div>
      </section>
    </MarketingShell>
  )
}
