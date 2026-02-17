'use client'

import Link from 'next/link'
import {
  BookOpen,
  Bot,
  Building2,
  CalendarClock,
  CheckCircle2,
  CreditCard,
  LifeBuoy,
  MessagesSquare,
  Settings,
  ShieldCheck,
  Smartphone,
  Users
} from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { SectionCard } from '@/components/shared/section-card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const tenantSetupSteps = [
  'Kayıt ol ve e-posta doğrulamasını tamamla.',
  'İlk girişte işletme (tenant) bilgilerini kontrol et.',
  'Botlarım > Yeni Bot Oluştur ile ilk botunu aç.',
  'Tool Kataloğu sayfasından gerekli toolları ekle.',
  'WhatsApp Kurulum adımlarını tamamlayarak mesaj akışını başlat.'
]

const tenantDailyFlow = [
  'Konuşmalar sayfasında gelen mesajları izle.',
  'Leadler ekranında müşteri kayıtlarını güncelle.',
  'Randevu/Not/Tool sayfalarından operasyonu yönet.',
  'Analitikler ve Kullanım ekranından performansı takip et.',
  'Ayarlar > Bildirimler/Güvenlik/API alanlarını düzenli kontrol et.'
]

const adminFlow = [
  'Super admin girişi için /admin/login kullan.',
  'Tenantlar ekranından müşteri tenantını seç.',
  'Müşteri Paneline Geç ile ilgili tenant context aç.',
  'Plan, tool, feature flag ve erişim yönetimini admin panelinden yap.',
  'Audit Logs ve Hata Merkezi ile operasyon kaydını denetle.'
]

const goLiveChecklist = [
  'Railway: DATABASE_URL, JWT_SECRET_KEY, FRONTEND_URL, BACKEND_URL dolu olmalı.',
  'Mail: EMAIL_ENABLED=true ve RESEND_API_KEY tanımlı olmalı.',
  'WhatsApp: META_APP_ID, META_APP_SECRET, META_CONFIG_ID eşleşmeli.',
  'Vercel: NEXT_PUBLIC_BACKEND_URL doğru backend domainine işaret etmeli.',
  'Prod güvenlik: SUPER_ADMIN_REQUIRE_2FA=true önerilir.'
]

export default function DashboardHelpPage() {
  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Nasıl Kullanılır"
          description="SvontAI kullanıcı paneli ve super admin operasyonları için hızlı kullanım rehberi."
          icon={<div className="rounded-2xl bg-primary/15 p-3 text-primary"><BookOpen className="h-6 w-6" /></div>}
          actions={<Badge variant="outline">In-App Guide</Badge>}
        />

        <SectionCard title="Hızlı Erişim" description="En sık kullanılan sayfalara kısa yol">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <Link href="/dashboard/bots"><Button variant="outline" className="w-full justify-start gap-2"><Bot className="h-4 w-4" /> Botlarım</Button></Link>
            <Link href="/dashboard/tools"><Button variant="outline" className="w-full justify-start gap-2"><Settings className="h-4 w-4" /> Tool Kataloğu</Button></Link>
            <Link href="/dashboard/leads"><Button variant="outline" className="w-full justify-start gap-2"><Users className="h-4 w-4" /> Leadler</Button></Link>
            <Link href="/dashboard/conversations"><Button variant="outline" className="w-full justify-start gap-2"><MessagesSquare className="h-4 w-4" /> Konuşmalar</Button></Link>
            <Link href="/dashboard/setup/whatsapp"><Button variant="outline" className="w-full justify-start gap-2"><Smartphone className="h-4 w-4" /> WhatsApp Kurulum</Button></Link>
            <Link href="/dashboard/help/whatsapp-setup"><Button variant="outline" className="w-full justify-start gap-2"><LifeBuoy className="h-4 w-4" /> WhatsApp Rehberi</Button></Link>
          </div>
        </SectionCard>

        <Tabs defaultValue="tenant" className="space-y-4">
          <TabsList>
            <TabsTrigger value="tenant">Kullanıcı Paneli</TabsTrigger>
            <TabsTrigger value="admin">Super Admin</TabsTrigger>
            <TabsTrigger value="golive">Canlıya Alma</TabsTrigger>
          </TabsList>

          <TabsContent value="tenant" className="space-y-4">
            <SectionCard
              title="İlk Kurulum (Yeni Kullanıcı)"
              description="Sistemi ilk kez açan müşteri için önerilen akış."
              actions={<Badge>5 adım</Badge>}
            >
              <div className="space-y-2">
                {tenantSetupSteps.map((step, index) => (
                  <div key={step} className="flex items-start gap-3 rounded-xl border border-border/70 bg-muted/30 px-4 py-3 text-sm">
                    <Badge variant="outline">{index + 1}</Badge>
                    <p>{step}</p>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard
              title="Günlük Operasyon Akışı"
              description="Ekibin her gün izlemesi gereken temel adımlar."
              actions={<Badge variant="secondary">Operasyon</Badge>}
            >
              <div className="space-y-2">
                {tenantDailyFlow.map((step) => (
                  <div key={step} className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
                    <p>{step}</p>
                  </div>
                ))}
              </div>
            </SectionCard>
          </TabsContent>

          <TabsContent value="admin" className="space-y-4">
            <SectionCard
              title="Super Admin Operasyon Akışı"
              description="Şirket tarafında tüm tenantları merkezi yönetmek için önerilen kullanım."
              actions={<Badge className="gap-1"><ShieldCheck className="h-3.5 w-3.5" /> Admin</Badge>}
            >
              <div className="space-y-2">
                {adminFlow.map((step, index) => (
                  <div key={step} className="flex items-start gap-3 rounded-xl border border-border/70 bg-muted/30 px-4 py-3 text-sm">
                    <Badge variant="outline">{index + 1}</Badge>
                    <p>{step}</p>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Önemli Notlar" description="Super admin erişiminde güvenlik standardı">
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" /> Super admin girişini sadece `Super Admin` portal modunda yap.</li>
                <li className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" /> Tenant context aktifken yaptığın işlemler seçili müşteriye uygulanır.</li>
                <li className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" /> Üretimde `SUPER_ADMIN_REQUIRE_2FA=true` kullan.</li>
              </ul>
            </SectionCard>
          </TabsContent>

          <TabsContent value="golive" className="space-y-4">
            <SectionCard
              title="Canlıya Alma Kontrol Listesi"
              description="Deploy sonrası temel kontrolleri bu sırayla yap."
              actions={<Badge variant="secondary"><CalendarClock className="mr-1 h-3.5 w-3.5" /> Go-Live</Badge>}
            >
              <div className="space-y-2">
                {goLiveChecklist.map((item) => (
                  <div key={item} className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
                    <p>{item}</p>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="İlgili Ekranlar" description="Canlı kontrol sırasında en çok kullanılan sayfalar">
              <div className="grid gap-3 sm:grid-cols-2">
                <Link href="/dashboard/usage"><Button variant="outline" className="w-full justify-start gap-2"><Building2 className="h-4 w-4" /> Kullanım ve Limitler</Button></Link>
                <Link href="/dashboard/billing"><Button variant="outline" className="w-full justify-start gap-2"><CreditCard className="h-4 w-4" /> Plan ve Abonelik</Button></Link>
              </div>
            </SectionCard>
          </TabsContent>
        </Tabs>
      </div>
    </ContentContainer>
  )
}
