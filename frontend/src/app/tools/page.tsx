import Link from 'next/link'
import { Bot, FileText, Mail, Route, ShieldCheck } from 'lucide-react'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

const tools = [
  { title: 'PDF ve doküman otomasyonu', description: 'PDF özetleme, dönüştürme ve rapor üretimi.', icon: FileText },
  { title: 'Gmail ve Drive akışları', description: 'E-posta özetleme ve dosya kaydetme işlerini otomatikleştirin.', icon: Mail },
  { title: 'Agent Router', description: 'Kullanıcı niyetine göre doğru aracı otomatik seçin.', icon: Route },
  { title: 'Güvenli otonomi', description: 'Riskli aksiyonlarda onay isteyen kontrollü otomasyon.', icon: ShieldCheck },
]

export default function ToolsRootPage() {
  return (
    <MarketingShell>
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <h1 className="text-4xl font-semibold">SvontAI Araç Kataloğu</h1>
          <p className="mt-4 text-muted-foreground">
            Ajans ve kurumsal ekipler için WhatsApp, doküman, e-posta ve CRM süreçlerini tek otonom çalışma katmanında birleştirin.
          </p>
          <div className="mt-6 flex gap-3">
            <Link href="/register"><Button>Ücretsiz Başla</Button></Link>
            <Link href="/contact"><Button variant="outline">Demo Planla</Button></Link>
          </div>
        </div>
        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {tools.map((tool) => {
            const Icon = tool.icon
            return (
              <Card key={tool.title}>
                <CardContent className="p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-6 w-6" />
                  </div>
                  <h2 className="mt-4 font-semibold">{tool.title}</h2>
                  <p className="mt-2 text-sm text-muted-foreground">{tool.description}</p>
                </CardContent>
              </Card>
            )
          })}
        </div>
        <div className="mt-12 rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3">
            <Bot className="h-5 w-5 text-primary" />
            <p className="text-sm text-muted-foreground">
              Kurulum sonrası SvontAI entegrasyon sağlığını izler, yeniden dener ve kullanıcı onayı gerektiren noktaları açıkça gösterir.
            </p>
          </div>
        </div>
      </section>
    </MarketingShell>
  )
}
