import type { Metadata } from 'next'
import Link from 'next/link'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ShieldCheck, Lock, KeyRound, FileCheck, Database, AlertOctagon } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Security',
  description: 'SvontAI güvenlik standardı: tenant izolasyonu, RBAC, audit log ve incident yönetimi.',
}

const securityItems = [
  {
    title: 'Tenant izolasyonu',
    description: 'Tüm sorgular tenant_id ile sınırlandırılır, IDOR engellenir.',
    icon: ShieldCheck,
  },
  {
    title: 'RBAC + Audit',
    description: 'Rol tabanlı erişim ve hassas aksiyonlar için audit log.',
    icon: FileCheck,
  },
  {
    title: 'Kayıtlı anahtarlar',
    description: 'API anahtarları şifrelenmiş saklama ve rotation süreçleri.',
    icon: KeyRound,
  },
  {
    title: 'Veri koruma',
    description: 'KVKK uyumlu süreçler ve hassas veri maskeleme.',
    icon: Database,
  },
  {
    title: 'Hesap koruması',
    description: 'Brute-force koruması, rate limit ve account lockout.',
    icon: Lock,
  },
  {
    title: 'Incident yönetimi',
    description: 'Olaylar için merkezi triage, postmortem ve SLA kayıtları.',
    icon: AlertOctagon,
  },
]

export default function SecurityPage() {
  return (
    <MarketingShell>
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <Reveal className="space-y-5">
          <Badge variant="outline">Güvenlik</Badge>
          <h1 className="text-4xl font-semibold">Enterprise güvenlik standardı</h1>
          <p className="text-muted-foreground">SvontAI, müşterilerinizin verisini ve süreçlerini güvenle yönetmeniz için tasarlandı.</p>
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
          <p className="mt-2 text-sm text-muted-foreground">Takımımız detaylı güvenlik dokümantasyonu ve SLA bilgilerini paylaşır.</p>
          <Link href="/contact" className="mt-6 inline-flex">
            <Button>Güvenlik Paketini İste</Button>
          </Link>
        </div>
      </section>
    </MarketingShell>
  )
}
