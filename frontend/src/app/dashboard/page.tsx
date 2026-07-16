'use client'

import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  Bot,
  CalendarCheck,
  CheckCircle2,
  LifeBuoy,
  MessageSquare,
  PhoneCall,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  Users,
} from 'lucide-react'
import { autopilotApi, conversationApi, leadApi } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ContentContainer } from '@/components/shared/content-container'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { KPIStat } from '@/components/shared/kpi-stat'
import { PageHeader } from '@/components/shared/page-header'
import { OperationalReportCard } from '@/components/dashboard/operational-report-card'

export default function DashboardPage() {
  const queryClient = useQueryClient()
  const { data: autopilotStatus, isLoading: autopilotLoading } = useQuery({
    queryKey: ['autopilot-status'],
    queryFn: () => autopilotApi.getStatus().then(res => res.data),
  })
  const { data: conversations, isLoading: conversationsLoading } = useQuery({
    queryKey: ['customer-dashboard-conversations'],
    queryFn: () => conversationApi.list({ limit: 5 }).then(res => res.data),
  })
  const { data: leads, isLoading: leadsLoading } = useQuery({
    queryKey: ['customer-dashboard-leads'],
    queryFn: () => leadApi.list({ limit: 5 }).then(res => res.data),
  })
  const runAutopilotMutation = useMutation({
    mutationFn: () => autopilotApi.run().then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['autopilot-status'] })
      queryClient.invalidateQueries({ queryKey: ['customer-dashboard-conversations'] })
      queryClient.invalidateQueries({ queryKey: ['customer-dashboard-leads'] })
    },
  })

  const requiredActions = autopilotStatus?.required_user_actions || []
  const healthScore = Number(autopilotStatus?.health_score || 0)
  const isReady = autopilotStatus?.status === 'ready'
  const businessProfileReady = autopilotStatus?.business_profile?.status === 'ready'
  const latestConversations = Array.isArray(conversations) ? conversations.slice(0, 3) : []
  const latestLeads = Array.isArray(leads) ? leads.slice(0, 3) : []

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="SmartWA Ana Panel"
          description="Sistem müşterilerinizle WhatsApp üzerinden ilgilenir; siz sadece gerekiyorsa izinleri tamamlarsınız."
          icon={<Icon3DBadge icon={ShieldCheck} from="from-primary" to="to-violet-500" />}
          actions={(
            <Button onClick={() => runAutopilotMutation.mutate()} disabled={runAutopilotMutation.isPending}>
              <RefreshCw className="mr-2 h-4 w-4" />
              {runAutopilotMutation.isPending ? 'Kontrol ediliyor...' : 'Sistemi Kontrol Et'}
            </Button>
          )}
        />

        <Card className="border border-border/70 shadow-soft">
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <div>
              <CardTitle>Sistem Durumu</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                SmartWA kurulum, sağlık kontrolü ve otomatik onarımları arka planda yürütür.
              </p>
            </div>
            <Badge variant={isReady ? 'success' : 'warning'}>
              {isReady ? 'Çalışıyor' : 'İzin Bekliyor'}
            </Badge>
          </CardHeader>
          <CardContent className="space-y-5">
            {autopilotLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-3">
                  <KPIStat label="Genel Sağlık" value={`${healthScore}/100`} icon={<ShieldCheck className="h-5 w-5" />} />
                  <KPIStat label="İşletme Bilgisi" value={businessProfileReady ? 'Hazır' : 'Ekibimizde'} icon={<CheckCircle2 className="h-5 w-5" />} />
                  <KPIStat label="Sizden Beklenen" value={requiredActions.length} icon={<AlertTriangle className="h-5 w-5" />} />
                </div>

                {requiredActions.length > 0 ? (
                  <div className="space-y-3">
                    <div className="rounded-xl border border-warning/40 bg-warning-subtle/30 p-4">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-5 w-5 text-warning" />
                        <div>
                          <h3 className="font-semibold">Devam etmek için izin gerekiyor</h3>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Meta WhatsApp veya ödeme gibi güvenliğiniz için sizin onayınız gereken adımlar var.
                          </p>
                        </div>
                      </div>
                    </div>
                    {requiredActions.slice(0, 3).map((action: any) => (
                      <div key={action.key} className="flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="font-medium">{action.label}</p>
                          <p className="text-sm text-muted-foreground">Bu tamamlanınca sistem otomatik devam eder.</p>
                        </div>
                        {action.url ? (
                          <Button asChild>
                            <Link href={action.url}>Tamamla</Link>
                          </Button>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-success/30 bg-success-subtle/30 p-4">
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="mt-0.5 h-5 w-5 text-success" />
                      <div>
                        <h3 className="font-semibold">Sizden bekleyen zorunlu işlem yok</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          SmartWA müşteri mesajları, sağlık kontrolleri ve otomatik toparlama akışlarını sürdürüyor.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <OperationalReportCard />

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Card className="border border-border/70 shadow-soft">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-500/10">
                <Bot className="h-6 w-6 text-violet-500" />
              </div>
              <div>
                <h3 className="font-semibold">Botlarım</h3>
                <p className="text-sm text-muted-foreground">Yanıtları ve bilgileri özelleştirin.</p>
                <Button asChild size="sm" variant="outline" className="mt-3">
                  <Link href="/dashboard/bots">Botları Aç</Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border border-border/70 shadow-soft">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                <Smartphone className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold">WhatsApp Bağlantısı</h3>
                <p className="text-sm text-muted-foreground">Numaranızı bağlayın, sistem devam etsin.</p>
                <Button asChild size="sm" variant="outline" className="mt-3">
                  <Link href="/dashboard/setup/whatsapp">Bağlantıyı Aç</Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border border-border/70 shadow-soft">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-info/10">
                <MessageSquare className="h-6 w-6 text-info" />
              </div>
              <div>
                <h3 className="font-semibold">Müşteri Mesajları</h3>
                <p className="text-sm text-muted-foreground">Gelen konuşmaları tek yerden izleyin.</p>
                <Button asChild size="sm" variant="outline" className="mt-3">
                  <Link href="/dashboard/conversations">Mesajları Aç</Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border border-border/70 shadow-soft">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-warning/10">
                <PhoneCall className="h-6 w-6 text-warning" />
              </div>
              <div>
                <h3 className="font-semibold">Aramalar</h3>
                <p className="text-sm text-muted-foreground">Çağrı kayıtlarını ve özetleri görün.</p>
                <Button asChild size="sm" variant="outline" className="mt-3">
                  <Link href="/dashboard/calls">Aramaları Aç</Link>
                </Button>
              </div>
            </CardContent>
          </Card>


          <Card className="border border-border/70 shadow-soft">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10">
                <CalendarCheck className="h-6 w-6 text-emerald-500" />
              </div>
              <div>
                <h3 className="font-semibold">Randevular</h3>
                <p className="text-sm text-muted-foreground">Alınan randevuları ve hatırlatmaları izleyin.</p>
                <Button asChild size="sm" variant="outline" className="mt-3">
                  <Link href="/dashboard/appointments">Randevuları Aç</Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border border-border/70 shadow-soft">
            <CardContent className="flex items-center gap-4 p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-success/10">
                <LifeBuoy className="h-6 w-6 text-success" />
              </div>
              <div>
                <h3 className="font-semibold">Destek</h3>
                <p className="text-sm text-muted-foreground">Bir şey gerektiğinde ekibimize yazın.</p>
                <Button asChild size="sm" variant="outline" className="mt-3">
                  <Link href="/dashboard/tickets">Destek Aç</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="border border-border/70 shadow-soft">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Son Mesajlar</CardTitle>
              <Button asChild variant="outline" size="sm">
                <Link href="/dashboard/conversations">Tümünü Gör</Link>
              </Button>
            </CardHeader>
            <CardContent>
              {conversationsLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : latestConversations.length === 0 ? (
                <EmptyState
                  icon={<MessageSquare className="h-8 w-8 text-primary" />}
                  title="Henüz mesaj yok"
                  description="WhatsApp bağlantısı tamamlandığında müşteri konuşmaları burada görünür."
                />
              ) : (
                <div className="space-y-3">
                  {latestConversations.map((conversation: any) => (
                    <Link key={conversation.id} href="/dashboard/conversations" className="block rounded-xl border p-4 hover:bg-muted/40">
                      <p className="font-medium">{conversation.customer_name || conversation.customer_phone || 'Müşteri'}</p>
                      <p className="mt-1 text-sm text-muted-foreground line-clamp-1">{conversation.last_message || 'Konuşma detayı'}</p>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border border-border/70 shadow-soft">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Müşteriler</CardTitle>
              <Button asChild variant="outline" size="sm">
                <Link href="/dashboard/leads">Tümünü Gör</Link>
              </Button>
            </CardHeader>
            <CardContent>
              {leadsLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : latestLeads.length === 0 ? (
                <EmptyState
                  icon={<Users className="h-8 w-8 text-primary" />}
                  title="Henüz müşteri kaydı yok"
                  description="SmartWA müşteri ilgisini yakaladığında kayıtlar burada görünür."
                />
              ) : (
                <div className="space-y-3">
                  {latestLeads.map((lead: any) => (
                    <div key={lead.id} className="rounded-xl border p-4">
                      <p className="font-medium">{lead.name || 'İsimsiz müşteri'}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{lead.phone || lead.email || 'İletişim bilgisi bekleniyor'}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </ContentContainer>
  )
}
