import type { Metadata } from 'next'
import Link from 'next/link'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { BookOpen, Terminal, ShieldCheck, FileText } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Docs',
  description: 'SvontAI dokümantasyonu: kurulum, API, güvenlik ve observability rehberleri.',
}

const docsSections = [
  {
    title: 'Başlangıç',
    description: 'Kurulum, tenant oluşturma ve ilk otomasyon adımları.',
    icon: BookOpen,
  },
  {
    title: 'API & Webhooks',
    description: 'REST uç noktaları, webhook doğrulama ve imza akışları.',
    icon: Terminal,
  },
  {
    title: 'Güvenlik',
    description: 'RBAC, audit log ve veri koruma standartları.',
    icon: ShieldCheck,
  },
  {
    title: 'Runbook',
    description: 'Incident triage, error center ve observability süreci.',
    icon: FileText,
  },
]

export default function DocsPage() {
  return (
    <MarketingShell>
      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
        <Reveal className="space-y-5">
          <Badge variant="outline">Dokümantasyon</Badge>
          <h1 className="text-4xl font-semibold">SvontAI dokümantasyonu</h1>
          <p className="text-muted-foreground">Teknik ekipler için rehberler, API referansı ve operasyon runbook'ları.</p>
        </Reveal>

        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {docsSections.map((item, index) => {
            const Icon = item.icon
            return (
              <Reveal key={item.title} delay={index * 80}>
                <Card className="border-border/60">
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

        <div className="mt-12 rounded-3xl border border-border/60 bg-card/60 p-8 text-center">
          <h2 className="text-2xl font-semibold">Tüm teknik dokümantasyon için giriş yapın</h2>
          <p className="mt-2 text-sm text-muted-foreground">Özel API anahtarları ve tenant rehberleri müşteri panelinde erişilebilir.</p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/login">
              <Button variant="outline">Giriş Yap</Button>
            </Link>
            <Link href="/register">
              <Button>Ücretsiz Başla</Button>
            </Link>
          </div>
        </div>
      </section>
    </MarketingShell>
  )
}
