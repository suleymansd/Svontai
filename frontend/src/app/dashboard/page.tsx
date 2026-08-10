'use client'

import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowRight,
  CalendarCheck,
  CheckCircle2,
  Clock3,
  Headphones,
  MessageSquare,
  PhoneOff,
  RefreshCw,
  ShieldCheck,
  Users,
  Workflow,
} from 'lucide-react'
import { analyticsApi, autopilotApi, conversationApi, leadApi } from '@/lib/api'
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
import { useRealtimeEvents } from '@/lib/use-realtime-events'

type ActionCenterItem = {
  id: string
  kind: 'human_handoff' | 'automation_failure' | 'voice_failure' | 'calendar_sync_failure' | string
  severity: 'high' | 'medium' | 'low' | string
  title: string
  description: string
  href: string
  cta_label: string
  occurred_at: string
}

type UpcomingAppointment = {
  id: string
  customer_name: string
  subject: string
  starts_at: string
  duration_minutes: number
  href: string
}

type ActionCenter = {
  generated_at: string
  window_hours: number
  required_count: number
  items: ActionCenterItem[]
  upcoming_appointments: UpcomingAppointment[]
}

const actionIcons = {
  human_handoff: Headphones,
  automation_failure: Workflow,
  voice_failure: PhoneOff,
  calendar_sync_failure: CalendarCheck,
}

export default function DashboardPage() {
  const queryClient = useQueryClient()
  useRealtimeEvents((event) => {
    const affectsDailyWork = ['message.', 'conversation.', 'automation.', 'appointment.', 'voice.']
      .some((prefix) => event.type.startsWith(prefix))
    if (!affectsDailyWork) return
    queryClient.invalidateQueries({ queryKey: ['customer-action-center'] })
    if (event.type.startsWith('message.') || event.type.startsWith('conversation.')) {
      queryClient.invalidateQueries({ queryKey: ['customer-dashboard-conversations'] })
      queryClient.invalidateQueries({ queryKey: ['customer-success'] })
    }
  })
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
  const { data: customerSuccess, isLoading: customerSuccessLoading } = useQuery({
    queryKey: ['customer-success', 30],
    queryFn: () => analyticsApi.getCustomerSuccess(30).then(res => res.data),
  })
  const { data: actionCenter, isLoading: actionCenterLoading, isError: actionCenterError } = useQuery<ActionCenter>({
    queryKey: ['customer-action-center', 24],
    queryFn: () => analyticsApi.getActionCenter(24).then(res => res.data),
  })
  const runAutopilotMutation = useMutation({
    mutationFn: () => autopilotApi.run().then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['autopilot-status'] })
      queryClient.invalidateQueries({ queryKey: ['customer-dashboard-conversations'] })
      queryClient.invalidateQueries({ queryKey: ['customer-dashboard-leads'] })
      queryClient.invalidateQueries({ queryKey: ['customer-action-center'] })
    },
  })

  const requiredActions = autopilotStatus?.required_user_actions || []
  const healthScore = Number(autopilotStatus?.health_score || 0)
  const isReady = autopilotStatus?.status === 'ready'
  const operationalItems = Array.isArray(actionCenter?.items) ? actionCenter.items : []
  const upcomingAppointments = Array.isArray(actionCenter?.upcoming_appointments)
    ? actionCenter.upcoming_appointments
    : []
  const attentionCount = requiredActions.length + Number(actionCenter?.required_count || 0)
  const systemNeedsAttention = attentionCount > 0 || actionCenterError
  const latestConversations = Array.isArray(conversations) ? conversations.slice(0, 3) : []
  const latestLeads = Array.isArray(leads) ? leads.slice(0, 3) : []

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Bugün"
          description="Müşteri hareketleri ve yalnızca sizin müdahalenizi gerektiren işler."
          icon={<Icon3DBadge icon={ShieldCheck} from="from-primary" to="to-violet-500" />}
          actions={(
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={isReady && !systemNeedsAttention ? 'success' : 'warning'}>
                {isReady && !systemNeedsAttention ? `Sistem çalışıyor • ${healthScore}/100` : `Kontrol gerekiyor • ${healthScore}/100`}
              </Badge>
              <Button
                variant="outline"
                data-analytics="dashboard_system_check"
                onClick={() => runAutopilotMutation.mutate()}
                disabled={runAutopilotMutation.isPending}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${runAutopilotMutation.isPending ? 'animate-spin' : ''}`} />
                Kontrol Et
              </Button>
            </div>
          )}
        />

        {autopilotLoading || actionCenterLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : systemNeedsAttention ? (
          <section className="border-y border-warning/40 bg-warning-subtle/20 py-5">
            <div className="mb-4 flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-warning" />
              <div>
                <h2 className="font-semibold">
                  {actionCenterError ? 'Günlük işler kontrol edilemedi' : `Müdahaleniz gereken ${attentionCount} işlem var`}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {actionCenterError
                    ? 'Veriler yeniden alınırken diğer otomasyonlar çalışmaya devam eder.'
                    : 'Öncelikli işlemi açın; güvenli otomasyonlar arka planda çalışmaya devam eder.'}
                </p>
              </div>
            </div>
            <div className="divide-y border-y bg-background">
              {requiredActions.slice(0, 4).map((action: any) => (
                <div key={`setup:${action.key}`} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <Badge variant="outline" className="mb-2">Kurulum</Badge>
                    <p className="text-sm font-medium">{action.label}</p>
                  </div>
                  {action.url ? <Button asChild size="sm"><Link href={action.url}>Tamamla</Link></Button> : null}
                </div>
              ))}
              {operationalItems.map((action) => {
                const ActionIcon = actionIcons[action.kind as keyof typeof actionIcons] || AlertTriangle
                return (
                  <div key={action.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <ActionIcon className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                      <div className="min-w-0">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold">{action.title}</p>
                          <Badge variant={action.severity === 'high' ? 'destructive' : 'warning'}>
                            {action.severity === 'high' ? 'Öncelikli' : 'Kontrol'}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">{action.description}</p>
                      </div>
                    </div>
                    <Button asChild size="sm" variant="outline" className="shrink-0">
                      <Link href={action.href}>{action.cta_label}<ArrowRight className="ml-2 h-4 w-4" /></Link>
                    </Button>
                  </div>
                )
              })}
              {actionCenterError ? (
                <div className="flex justify-end p-4">
                  <Button variant="outline" size="sm" onClick={() => queryClient.invalidateQueries({ queryKey: ['customer-action-center'] })}>
                    <RefreshCw className="mr-2 h-4 w-4" /> Yeniden Dene
                  </Button>
                </div>
              ) : null}
            </div>
          </section>
        ) : (
          <section className="flex items-start gap-3 border-y border-success/30 bg-success-subtle/20 py-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 text-success" />
            <div>
              <h2 className="font-semibold">Müdahale gerekmiyor</h2>
              <p className="text-sm text-muted-foreground">Mesajlar ve otomasyonlar arka planda çalışıyor.</p>
            </div>
          </section>
        )}

        {upcomingAppointments.length > 0 ? (
          <section className="space-y-3">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Önümüzdeki 24 saat</h2>
                <p className="text-sm text-muted-foreground">Yaklaşan müşteri randevuları.</p>
              </div>
              <Button asChild variant="ghost" size="sm">
                <Link href="/dashboard/appointments">Takvimi Aç<ArrowRight className="ml-2 h-4 w-4" /></Link>
              </Button>
            </div>
            <div className="divide-y border-y">
              {upcomingAppointments.slice(0, 3).map((appointment) => (
                <Link
                  key={appointment.id}
                  href={appointment.href}
                  className="flex flex-col gap-1 py-3 transition-colors hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between sm:px-3"
                >
                  <div>
                    <p className="text-sm font-semibold">{appointment.customer_name}</p>
                    <p className="text-sm text-muted-foreground">{appointment.subject}</p>
                  </div>
                  <div className="text-sm font-medium">
                    {new Date(appointment.starts_at).toLocaleString('tr-TR', {
                      day: '2-digit',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                    <span className="ml-2 text-muted-foreground">{appointment.duration_minutes} dk</span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ) : null}

        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Son 30 gün</h2>
            <p className="text-sm text-muted-foreground">Gerçek müşteri ve işlem kayıtlarından hesaplanır.</p>
          </div>
          {customerSuccessLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KPIStat label="Otomatik Yanıt" value={customerSuccess?.ai_replies || 0} icon={<MessageSquare className="h-5 w-5" />} />
              <KPIStat label="Yeni Müşteri" value={customerSuccess?.new_customers || 0} icon={<Users className="h-5 w-5" />} />
              <KPIStat label="Randevu" value={customerSuccess?.appointments || 0} icon={<CalendarCheck className="h-5 w-5" />} />
              <KPIStat
                label="Kazanılan Zaman"
                value={`${Math.round(Number(customerSuccess?.estimated_time_saved_minutes || 0) / 6) / 10} saat`}
                icon={<Clock3 className="h-5 w-5" />}
              />
            </div>
          )}
        </section>

        <OperationalReportCard />

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
