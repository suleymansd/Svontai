import type { Metadata } from 'next'
import Link from 'next/link'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ShieldCheck, Lock, KeyRound, FileCheck, Database, AlertOctagon, Gauge, Webhook } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Security',
  description: 'SmartWA güvenlik yaklaşımı: tenant izolasyonu, RBAC, audit log, rate limit, webhook imza kontrolü ve incident yönetimi.',
}

const securityItems = [
  {
    title: 'Tenant izolasyonu',
    description: 'Müşteri verileri tenant kapsamıyla ayrılır; endpointlerde tenant context ve RBAC kontrolleri uygulanır.',
    icon: ShieldCheck,
  },
  {
    title: 'RBAC + Audit',
    description: 'Rol tabanlı erişim, admin context ayrımı ve hassas aksiyonlar için audit/system event kayıtları tutulur.',
    icon: FileCheck,
  },
  {
    title: 'Secret yönetimi',
    description: 'Prod ortamda insecure default secret ile startup engellenir; webhook ve entegrasyon secretları env üzerinden yönetilir.',
    icon: KeyRound,
  },
  {
    title: 'Veri koruma',
    description: 'Erişim, düzeltme, silme ve destek talepleri için operasyonel süreçler ve kayıt mekanizmaları bulunur.',
    icon: Database,
  },
  {
    title: 'Rate limit',
    description: 'Auth, public chat, webhook, tool/assistant ve test araması uçlarında abuse limitleri uygulanır.',
    icon: Gauge,
  },
  {
    title: 'Webhook doğrulama',
    description: 'Prod ortamda Meta webhook POST çağrıları imza kontrolünden geçer; alias webhook basic auth ile korunur.',
    icon: Webhook,
  },
  {
    title: 'Hesap koruması',
    description: 'Brute-force koruması, refresh cookie, kısa ömürlü access token ve hesap kilitleme akışları desteklenir.',
    icon: Lock,
  },
  {
    title: 'Incident yönetimi',
    description: 'Provider veya otomasyon sorunları için incident/ticket üretimi ve runbook odaklı operasyon akışı bulunur.',
    icon: AlertOctagon,
  },
]

export default function SecurityPage() {
  return (
    <MarketingShell>
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <Reveal className="space-y-5">
          <Badge variant="outline">Güvenlik</Badge>
          <h1 className="text-4xl font-semibold">Güvenli otonomi yaklaşımı</h1>
          <p className="text-muted-foreground">SmartWA; müşteri operasyonlarını otomatik yürütürken riskli aksiyonlarda onay, güçlü tenant ayrımı, rate limit ve izlenebilir audit kayıtlarıyla çalışacak şekilde tasarlandı.</p>
        </Reveal>

        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {securityItems.map((item, index) => {
            const Icon = item.icon
            return (
              <Reveal key={item.title} delay={index * 80}>
                <Card className="h-full border-border/60">
                  <CardContent className="p-6">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                      <Icon className="h-6 w-6" />
                    </div>
                    <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
                    <p className="mt-2 text-sm text-muted-foreground">{item.description}</p>
                  </CardContent>
                </Card>
              </Reveal>
            )
          })}
        </div>

        <div className="mt-16 rounded-3xl border border-border/60 bg-card/60 p-10 text-center">
          <h2 className="text-2xl font-semibold">Güvenlik değerlendirmesi mi gerekiyor?</h2>
          <p className="mt-2 text-sm text-muted-foreground">Takımımız entegrasyon, veri akışı, yetki modeli ve canlıya alma kontrol listesini paylaşır.</p>
          <Link href="/contact" className="mt-6 inline-flex">
            <Button>Güvenlik Görüşmesi İste</Button>
          </Link>
        </div>
      </section>
    </MarketingShell>
  )
}
