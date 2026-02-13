import type { Metadata } from 'next'
import Link from 'next/link'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ShieldCheck, Bot, Workflow, LineChart, MessageSquare, AlertTriangle } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Features',
  description: 'SvontAI modüler mimariyle müşteri portalı, admin ops ve observability katmanlarını birleştirir.',
}

const featureGroups = [
  {
    title: 'Customer Portal',
    description: 'Takım yönetimi, ticket akışları, kullanım ve otomasyon geçmişi.',
    icon: MessageSquare,
  },
  {
    title: 'Company Panel',
    description: 'Tenant yönetimi, planlar, tools katalogu ve audit loglar.',
    icon: ShieldCheck,
  },
  {
    title: 'Observability',
    description: 'Run hataları, webhook sorunları, incident triage ve SLA.',
    icon: AlertTriangle,
  },
  {
    title: 'Automation Studio',
    description: 'n8n akışları, araç katalogu ve event correlation.',
    icon: Workflow,
  },
  {
    title: 'AI Assistants',
    description: 'Bilgi tabanı, tone ayarları ve operatör devir akışları.',
    icon: Bot,
  },
  {
    title: 'Insights',
    description: 'Kullanım metrikleri, KPI kartları ve trend raporları.',
    icon: LineChart,
  },
]

export default function FeaturesPage() {
  return (
    <MarketingShell>
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <Reveal className="space-y-5">
          <Badge variant="outline">Özellikler</Badge>
          <h1 className="text-4xl font-semibold">SvontAI modüler mimariyle büyür</h1>
          <p className="text-muted-foreground">Tüm ürün modülleri tek bir tasarım sistemi ve API sözleşmesiyle çalışır.</p>
        </Reveal>

        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {featureGroups.map((feature, index) => {
            const Icon = feature.icon
            return (
              <Reveal key={feature.title} delay={index * 80}>
                <Card className="h-full border-border/60">
                  <CardContent className="p-6">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                      <Icon className="h-6 w-6" />
                    </div>
                    <h3 className="mt-4 text-lg font-semibold">{feature.title}</h3>
                    <p className="mt-2 text-sm text-muted-foreground">{feature.description}</p>
                  </CardContent>
                </Card>
              </Reveal>
            )
          })}
        </div>

        <div className="mt-16 rounded-3xl border border-border/60 bg-card/60 p-10 text-center">
          <h2 className="text-2xl font-semibold">SvontAI ile ekibinizi tek panelde toplayın</h2>
          <p className="mt-2 text-sm text-muted-foreground">Customer portal, admin ops ve observability bir arada.</p>
          <Link href="/contact" className="mt-6 inline-flex">
            <Button>Demo Planla</Button>
          </Link>
        </div>
      </section>
    </MarketingShell>
  )
}
