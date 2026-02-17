'use client'

import Link from 'next/link'
import {
  BookOpen,
  CheckCircle2,
  ShieldCheck,
  Building2,
  Boxes,
  Package,
  LifeBuoy,
  AlertTriangle
} from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { SectionCard } from '@/components/shared/section-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const adminRunbook = [
  'Admin login: /admin/login (super admin portal modu).',
  'Tenantlar sayfasından müşteri tenantını seç ve context ata.',
  'Gerekirse Müşteri Paneline Geç ile tenant içi ekranları denetle.',
  'Plan/Tool/Feature Flag değişikliklerini admin ekranından uygula.',
  'Audit Logs üzerinden kritik değişiklikleri doğrula.'
]

const incidentFlow = [
  'Hata Merkezi ve Incidents ekranından problemi tespit et.',
  'Etkilenen tenantı belirleyip tenant detayına gir.',
  'Gerekirse tenant bazlı geçici kapatma/açma işlemi uygula.',
  'Ticket kaydı açıp çözüm notunu operasyon ekibiyle paylaş.'
]

export default function AdminHelpPage() {
  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Super Admin Kullanım Rehberi"
          description="Şirket yönetimi için merkezi operasyon akışı ve hızlı işlem adımları."
          icon={<div className="rounded-2xl bg-primary/15 p-3 text-primary"><BookOpen className="h-6 w-6" /></div>}
          actions={<Badge><ShieldCheck className="mr-1 h-3.5 w-3.5" /> Admin Guide</Badge>}
        />

        <SectionCard title="Günlük Super Admin Akışı" description="Tüm tenant yönetimi için önerilen standart süreç">
          <div className="space-y-2">
            {adminRunbook.map((step, index) => (
              <div key={step} className="flex items-start gap-3 rounded-xl border border-border/70 bg-muted/30 px-4 py-3 text-sm">
                <Badge variant="outline">{index + 1}</Badge>
                <p>{step}</p>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Operasyon Kısayolları" description="En sık kullanılan admin ekranları">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <Link href="/admin/tenants"><Button variant="outline" className="w-full justify-start gap-2"><Building2 className="h-4 w-4" /> Tenant Yönetimi</Button></Link>
            <Link href="/admin/plans"><Button variant="outline" className="w-full justify-start gap-2"><Package className="h-4 w-4" /> Plan Yönetimi</Button></Link>
            <Link href="/admin/tools"><Button variant="outline" className="w-full justify-start gap-2"><Boxes className="h-4 w-4" /> Tool Yönetimi</Button></Link>
            <Link href="/admin/errors"><Button variant="outline" className="w-full justify-start gap-2"><AlertTriangle className="h-4 w-4" /> Hata Merkezi</Button></Link>
            <Link href="/admin/tickets"><Button variant="outline" className="w-full justify-start gap-2"><LifeBuoy className="h-4 w-4" /> Tickets</Button></Link>
            <Link href="/dashboard/help"><Button variant="outline" className="w-full justify-start gap-2"><BookOpen className="h-4 w-4" /> Kullanıcı Rehberi</Button></Link>
          </div>
        </SectionCard>

        <SectionCard title="Incident Müdahale Akışı" description="Canlı sorunlarda izlenecek minimum prosedür">
          <div className="space-y-2 text-sm">
            {incidentFlow.map((item) => (
              <div key={item} className="flex items-start gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
                <p>{item}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </ContentContainer>
  )
}
