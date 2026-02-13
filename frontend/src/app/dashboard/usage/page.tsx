'use client'

import { useQuery } from '@tanstack/react-query'
import { Check, X, Gauge, Calendar, Sparkles } from 'lucide-react'
import { subscriptionApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { SectionCard } from '@/components/shared/section-card'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/shared/empty-state'
import Link from 'next/link'

const featureLabels: Record<string, string> = {
  whatsapp_integration: 'WhatsApp Entegrasyonu',
  analytics: 'Detaylı Analitikler',
  custom_branding: 'Özel Markalama',
  priority_support: 'Öncelikli Destek',
  api_access: 'API Erişimi',
  export_data: 'Veri Dışa Aktarma',
  operator_takeover: 'Operatör Devralma',
  lead_automation: 'Otomatik Lead Yakalama',
  white_label: 'White Label',
  dedicated_support: 'Özel Müşteri Temsilcisi',
}

export default function UsagePage() {
  const { data: usage, isLoading, isError, refetch } = useQuery({
    queryKey: ['usage-stats'],
    queryFn: () => subscriptionApi.getUsageStats().then(res => res.data),
  })

  if (isError) {
    return (
      <ContentContainer>
        <EmptyState
          title="Kullanım verileri alınamadı"
          description="Tekrar deneyin veya destek ekibine ulaşın."
          action={(
            <div className="flex items-center gap-3">
              <Button onClick={() => refetch()}>Tekrar Dene</Button>
              <Link href="/dashboard/billing">
                <Button variant="outline">Planları Gör</Button>
              </Link>
            </div>
          )}
        />
      </ContentContainer>
    )
  }

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Kullanım"
          description="Plan limitleri, kalan kullanım ve özellik durumlarını inceleyin."
          actions={(
            <Link href="/dashboard/billing">
              <Button variant="outline">Planları Yönet</Button>
            </Link>
          )}
        />

        {isLoading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, idx) => (
              <Card key={`usage-skeleton-${idx}`}>
                <CardContent className="p-6">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="mt-3 h-8 w-24" />
                  <Skeleton className="mt-2 h-3 w-20" />
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {!isLoading && !usage && (
          <EmptyState
            title="Kullanım verisi yok"
            description="Abonelik planınız oluşturulmadı." 
            action={(
              <Link href="/dashboard/billing">
                <Button>Planları Görüntüle</Button>
              </Link>
            )}
          />
        )}

        {!isLoading && usage && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KPIStat
                label="Mesaj Kullanımı"
                value={`${usage.messages_used} / ${usage.message_limit}`}
                trend={`${usage.message_usage_percent}% kullanıldı`}
                tone={usage.message_usage_percent > 80 ? 'warning' : 'neutral'}
                icon={<Gauge className="h-5 w-5" />}
              />
              <KPIStat
                label="Kalan Mesaj"
                value={usage.messages_remaining}
                trend="Bu ay"
                icon={<Sparkles className="h-5 w-5" />}
              />
              <KPIStat
                label="Bot Limiti"
                value={usage.bot_limit}
                trend="Aktif plan"
                icon={<Gauge className="h-5 w-5" />}
              />
              <KPIStat
                label="Bilgi Tabanı"
                value={usage.knowledge_limit}
                trend="Öğe limiti"
                icon={<Gauge className="h-5 w-5" />}
              />
            </div>

            <SectionCard
              title="Plan Özeti"
              description="Abonelik durumunuz ve dönem bilgileriniz."
            >
              <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge variant={usage.status === 'trial' ? 'warning' : 'default'}>
                      {usage.status === 'trial' ? 'Deneme' : usage.status}
                    </Badge>
                    <h3 className="text-lg font-semibold">{usage.plan_name}</h3>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">Plan türü: {usage.plan_type}</p>
                  <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted-foreground">
                    {usage.trial_ends_at && (
                      <span className="flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        Deneme bitiş: {new Date(usage.trial_ends_at).toLocaleDateString('tr-TR')}
                      </span>
                    )}
                    {usage.current_period_end && (
                      <span className="flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        Dönem bitiş: {new Date(usage.current_period_end).toLocaleDateString('tr-TR')}
                      </span>
                    )}
                  </div>
                </div>
                <div className="w-full max-w-sm">
                  <div className="flex items-center justify-between text-sm">
                    <span>Mesaj Kullanımı</span>
                    <span className="text-muted-foreground">{usage.message_usage_percent}%</span>
                  </div>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={usage.message_usage_percent > 80 ? 'h-full bg-destructive' : 'h-full bg-primary'}
                      style={{ width: `${Math.min(100, usage.message_usage_percent)}%` }}
                    />
                  </div>
                </div>
              </div>
            </SectionCard>

            <SectionCard
              title="Plan Özellikleri"
              description="Aktif planınızda kullanılabilir özellikler."
            >
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(featureLabels).map(([key, label]) => {
                  const enabled = usage.features?.[key] !== false
                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-xl border border-border/70 px-4 py-3"
                    >
                      <span className="text-sm font-medium">{label}</span>
                      <span className={enabled ? 'text-success' : 'text-muted-foreground'}>
                        {enabled ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
                      </span>
                    </div>
                  )
                })}
              </div>
            </SectionCard>
          </>
        )}
      </div>
    </ContentContainer>
  )
}
