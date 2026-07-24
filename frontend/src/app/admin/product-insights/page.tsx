'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BarChart3, MousePointerClick, Route, Users } from 'lucide-react'

import { productAnalyticsApi } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ContentContainer } from '@/components/shared/content-container'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { KPIStat } from '@/components/shared/kpi-stat'
import { PageHeader } from '@/components/shared/page-header'
import { SectionCard } from '@/components/shared/section-card'
import { Skeleton } from '@/components/ui/skeleton'

type CountItem = { name: string; count: number }
type PathItem = { path: string; count: number }
type FrictionItem = { name: string; path?: string | null; count: number }
type FunnelItem = { name: string; sessions: number }

type ProductInsights = {
  period_days: number
  total_events: number
  active_sessions: number
  active_users: number
  top_paths: PathItem[]
  top_events: CountItem[]
  friction: FrictionItem[]
  funnel: FunnelItem[]
}

const eventLabels: Record<string, string> = {
  dashboard_viewed: 'Ana panel görüntülendi',
  assistant_simulator_opened: 'Simülatör açıldı',
  assistant_simulator_message: 'Simülatörde mesaj denendi',
  whatsapp_setup_opened: 'WhatsApp kurulumu açıldı',
  onboarding_completed: 'Kurulum tamamlandı',
  api_error: 'API hatası',
  simulator_error: 'Simülatör hatası',
}

export default function ProductInsightsPage() {
  const [days, setDays] = useState(30)
  const { data, isLoading } = useQuery<ProductInsights>({
    queryKey: ['global-product-insights', days],
    queryFn: () => productAnalyticsApi.getGlobalFriction(days).then((response) => response.data),
  })

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Ürün İçgörüleri"
          description="Kişisel içerik toplamadan kullanıcıların zorlandığı ekranları ve kurulum hunisini izleyin."
          icon={<Icon3DBadge icon={BarChart3} from="from-cyan-500" to="to-emerald-500" />}
          actions={(
            <div className="flex gap-2">
              {[7, 30, 90].map((period) => (
                <Button key={period} size="sm" variant={days === period ? 'default' : 'outline'} onClick={() => setDays(period)}>
                  {period} gün
                </Button>
              ))}
            </div>
          )}
        />

        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              <KPIStat label="Aktif kullanıcı" value={data?.active_users || 0} icon={<Users className="h-5 w-5" />} />
              <KPIStat label="Oturum" value={data?.active_sessions || 0} icon={<MousePointerClick className="h-5 w-5" />} />
              <KPIStat label="Etkileşim" value={data?.total_events || 0} icon={<BarChart3 className="h-5 w-5" />} />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Kurulum ve kullanım hunisi" description="Her adımı gören benzersiz oturum sayısı">
                <div className="space-y-3">
                  {(data?.funnel || []).map((item, index) => {
                    const maximum = Math.max(1, ...(data?.funnel || []).map((entry) => entry.sessions))
                    return (
                      <div key={item.name}>
                        <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                          <span>{eventLabels[item.name] || item.name}</span>
                          <span className="font-medium">{item.sessions}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full bg-primary"
                            style={{ width: `${Math.max(item.sessions > 0 ? 5 : 0, (item.sessions / maximum) * 100)}%`, opacity: 1 - index * 0.1 }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </SectionCard>

              <SectionCard title="Dikkat gereken noktalar" description="Hata veya yarım kalan akış sinyalleri">
                {!data?.friction?.length ? (
                  <EmptyState title="Belirgin sorun yok" description="Seçilen dönemde kullanıcı sürtünmesi kaydedilmedi." />
                ) : (
                  <div className="space-y-3">
                    {data.friction.map((item) => (
                      <div key={`${item.name}-${item.path}`} className="flex items-start justify-between gap-3 border-b pb-3 last:border-0">
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" />
                          <div>
                            <p className="text-sm font-medium">{eventLabels[item.name] || item.name}</p>
                            <p className="text-xs text-muted-foreground">{item.path || 'Genel işlem'}</p>
                          </div>
                        </div>
                        <Badge variant="warning">{item.count}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>

              <SectionCard title="En çok kullanılan ekranlar" description="Sorgu parametreleri ve form içerikleri kaydedilmez">
                <div className="space-y-3">
                  {(data?.top_paths || []).map((item) => (
                    <div key={item.path} className="flex items-center justify-between gap-3 border-b pb-3 last:border-0">
                      <div className="flex min-w-0 items-center gap-2">
                        <Route className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <code className="truncate text-xs">{item.path}</code>
                      </div>
                      <span className="text-sm font-medium">{item.count}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>

              <SectionCard title="En sık işlemler" description="Anonimleştirilmiş ürün olayları">
                <div className="space-y-3">
                  {(data?.top_events || []).map((item) => (
                    <div key={item.name} className="flex items-center justify-between gap-3 border-b pb-3 last:border-0">
                      <span className="text-sm">{eventLabels[item.name] || item.name}</span>
                      <span className="text-sm font-medium">{item.count}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            </div>
          </>
        )}
      </div>
    </ContentContainer>
  )
}
