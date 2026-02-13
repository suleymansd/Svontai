import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Check } from 'lucide-react'

const useCaseMap: Record<string, { title: string; subtitle: string; highlights: string[]; flows: string[] }> = {
  'real-estate': {
    title: 'Emlak otomasyonları',
    subtitle: 'Portföy talebi, randevu ve takip süreçlerini otomatikleştirin.',
    highlights: ['Portföy eşleştirme', 'Randevu planlama', 'Lead skorlaması'],
    flows: ['Yeni ilan bildirimi', 'Uygun portföy önerisi', 'Gezdirme onayı'],
  },
  'clinics': {
    title: 'Klinik & sağlık',
    subtitle: 'Randevu, hasta bilgilendirme ve takip süreçlerini tek panelde yönetin.',
    highlights: ['Randevu hatırlatma', 'Doktor yönlendirme', 'Hasta memnuniyet akışı'],
    flows: ['Ön bilgi formu', 'Randevu onayı', 'Tedavi sonrası takip'],
  },
  'restaurants': {
    title: 'Restoran operasyonları',
    subtitle: 'Rezervasyon, kampanya ve teslimat akışlarını otomatikleştirin.',
    highlights: ['Rezervasyon otomasyonu', 'Menü önerileri', 'Sadakat programı'],
    flows: ['Rezervasyon talebi', 'Masaya yönlendirme', 'Kampanya bildirimi'],
  },
}

interface UseCasePageProps {
  params: { segment: string }
}

export async function generateMetadata({ params }: UseCasePageProps): Promise<Metadata> {
  const data = useCaseMap[params.segment]
  if (!data) {
    return { title: 'Use Case' }
  }
  return {
    title: data.title,
    description: data.subtitle,
  }
}

export default function UseCasePage({ params }: UseCasePageProps) {
  const data = useCaseMap[params.segment]
  if (!data) {
    notFound()
  }

  return (
    <MarketingShell>
      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
        <Reveal className="space-y-5">
          <Badge variant="outline">Use Case</Badge>
          <h1 className="text-4xl font-semibold">{data.title}</h1>
          <p className="text-muted-foreground">{data.subtitle}</p>
        </Reveal>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <Card className="border-border/60">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold">Öne çıkan yetenekler</h3>
              <div className="mt-4 space-y-2 text-sm">
                {data.highlights.map((item) => (
                  <div key={item} className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-success" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card className="border-border/60">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold">Otomasyon akışları</h3>
              <div className="mt-4 space-y-2 text-sm">
                {data.flows.map((item) => (
                  <div key={item} className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-primary" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mt-12 rounded-3xl border border-border/60 bg-card/60 p-8 text-center">
          <h2 className="text-2xl font-semibold">İhtiyacınıza özel akışlar tasarlayalım</h2>
          <p className="mt-2 text-sm text-muted-foreground">Ekipleriniz için doğru otomasyonları birlikte seçelim.</p>
          <Link href="/contact" className="mt-6 inline-flex">
            <Button>Demo Talep Et</Button>
          </Link>
        </div>
      </section>
    </MarketingShell>
  )
}
