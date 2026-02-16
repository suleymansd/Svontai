'use client'

import { useQuery } from '@tanstack/react-query'
import {
  MessageSquare,
  Users,
  Bot,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  BarChart3,
  PieChart,
  Calendar,
  Lock
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { analyticsApi, subscriptionApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import Link from 'next/link'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

interface DashboardStats {
  today: {
    messages_sent: number
    messages_received: number
    ai_responses: number
    conversations_started: number
    leads_captured: number
  }
  weekly: {
    messages_sent: number
    messages_received: number
    conversations_started: number
    leads_captured: number
  }
  monthly: {
    messages_sent: number
    messages_received: number
    conversations_started: number
    leads_captured: number
  }
  totals: {
    conversations: number
    leads: number
  }
}

interface ChartDataPoint {
  date: string
  messages_sent: number
  messages_received: number
  ai_responses: number
  conversations: number
  leads: number
}

function sumKey(data: ChartDataPoint[], key: keyof ChartDataPoint): number {
  return data.reduce((sum, item) => sum + (item[key] as number), 0)
}

function percentChange(current: number, previous: number): number | undefined {
  if (!previous) return undefined
  return Math.round(((current - previous) / previous) * 100)
}

function changeLast7VsPrev7(data: ChartDataPoint[], key: keyof ChartDataPoint): number | undefined {
  if (!data || data.length < 14) return undefined
  const slice = data.slice(-14)
  const prev = sumKey(slice.slice(0, 7), key)
  const curr = sumKey(slice.slice(7), key)
  return percentChange(curr, prev)
}

function StatCard({
  title,
  value,
  change,
  changeLabel,
  icon: Icon,
  color
}: {
  title: string
  value: number | string
  change?: number
  changeLabel?: string
  icon: React.ElementType
  color: string
}) {
  const isPositive = change && change >= 0

  return (
    <Card className="card-hover-lift gradient-border-animated">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground mb-1">{title}</p>
            <p className="text-3xl font-bold">{value}</p>
            {change !== undefined && (
              <div className={cn(
                'flex items-center gap-1 mt-2 text-sm',
                isPositive ? 'text-green-600' : 'text-red-600'
              )}>
                {isPositive ? (
                  <ArrowUpRight className="w-4 h-4" />
                ) : (
                  <ArrowDownRight className="w-4 h-4" />
                )}
                <span className="font-medium">{Math.abs(change)}%</span>
                {changeLabel && (
                  <span className="text-muted-foreground">{changeLabel}</span>
                )}
              </div>
            )}
          </div>
          <div className={cn(
            'w-12 h-12 rounded-2xl flex items-center justify-center animate-pulse-glow',
            color
          )}>
            <Icon className="w-6 h-6 text-white" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function MiniChart({ data, dataKey, color }: { data: ChartDataPoint[], dataKey: keyof ChartDataPoint, color: string }) {
  if (!data || data.length === 0) return null

  const values = data.map(d => d[dataKey] as number)
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1

  return (
    <div className="flex items-end gap-1 h-16">
      {data.slice(-14).map((point, index) => {
        const height = ((point[dataKey] as number - min) / range) * 100
        return (
          <div
            key={index}
            className={cn('flex-1 rounded-t transition-all duration-300 hover:opacity-80 hover:scale-y-105 origin-bottom', color)}
            style={{ height: `${Math.max(height, 5)}%` }}
            title={`${point.date}: ${point[dataKey]}`}
          />
        )
      })}
    </div>
  )
}

export default function AnalyticsPage() {
  const { data: usageStats, isLoading: usageLoading } = useQuery({
    queryKey: ['usage-stats'],
    queryFn: () => subscriptionApi.getUsageStats().then(res => res.data),
  })

  const analyticsEnabled = usageStats?.features?.analytics === true
  const analyticsKnown = usageStats?.features?.analytics !== undefined
  const analyticsLocked = analyticsKnown && !analyticsEnabled

  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: () => analyticsApi.getDashboardStats().then(res => res.data),
  })

  const { data: chartData, isLoading: chartLoading } = useQuery<ChartDataPoint[]>({
    queryKey: ['chart-data'],
    queryFn: () => analyticsApi.getChartData(30).then(res => res.data),
    enabled: analyticsEnabled,
  })

  const isLoading = statsLoading || (analyticsEnabled && chartLoading) || usageLoading
  const hasData = Boolean(
    stats
      && (
        stats.totals.conversations > 0
        || stats.totals.leads > 0
        || stats.monthly.messages_sent > 0
        || stats.monthly.messages_received > 0
        || stats.monthly.conversations_started > 0
        || stats.monthly.leads_captured > 0
        || stats.today.ai_responses > 0
      )
  )

  const totalMonthlyMessages = (stats?.monthly.messages_sent || 0) + (stats?.monthly.messages_received || 0)
  const todayTotalMessages = (stats?.today.messages_sent || 0) + (stats?.today.messages_received || 0)

  const messagesChange = chartData ? changeLast7VsPrev7(chartData, 'messages_sent') : undefined
  const leadsChange = chartData ? changeLast7VsPrev7(chartData, 'leads') : undefined
  const conversationsChange = chartData ? changeLast7VsPrev7(chartData, 'conversations') : undefined
  const aiResponses30d = chartData ? sumKey(chartData, 'ai_responses') : undefined

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Analitikler"
          description={analyticsLocked ? "Temel metrikleri görüntüleyin (detaylı grafikler ücretli planda)." : "İşletmenizin performansını detaylı inceleyin."}
          icon={<Icon3DBadge icon={BarChart3} from="from-indigo-500" to="to-violet-500" />}
          actions={(
            analyticsLocked ? (
              <Badge variant="outline" className="gap-1">
                <Lock className="w-3 h-3" />
                Temel Analitik
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1">
                <Calendar className="w-3 h-3" />
                Son 30 Gün
              </Badge>
            )
          )}
        />

        {!analyticsEnabled && analyticsKnown && (
          <Card className="border-amber-200 dark:border-amber-800">
            <CardContent className="p-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <div className="mt-1 w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                  <Lock className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="font-semibold">Detaylı analitikler kilitli</p>
                  <p className="text-sm text-muted-foreground">Grafikler ve karşılaştırmalar için plan yükseltin.</p>
                </div>
              </div>
              <Link href="/dashboard/billing">
                <Button className="bg-gradient-to-r from-amber-600 to-orange-600">Planları Görüntüle</Button>
              </Link>
            </CardContent>
          </Card>
        )}

        {!isLoading && !hasData && (
          <EmptyState
            icon={<BarChart3 className="h-6 w-6 text-primary" />}
            title="Henüz analitik verisi yok"
            description="Botunuzdan mesaj geldikçe, konuşmalar başladıkça ve lead oluştukça burada raporlar oluşur."
            action={(
              <div className="flex flex-wrap justify-center gap-2">
                <Link href="/dashboard/bots"><Button>Botlara Git</Button></Link>
                <Link href="/dashboard/leads"><Button variant="outline">Leadler</Button></Link>
              </div>
            )}
          />
        )}

        {/* Quick Stats */}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {isLoading ? (
            [...Array(4)].map((_, i) => (
              <Card key={i}>
                <CardContent className="p-6">
                  <div className="space-y-3">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-8 w-16" />
                    <Skeleton className="h-4 w-32" />
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <>
              <StatCard
                title="Bu Ay Mesaj"
                value={totalMonthlyMessages}
                change={analyticsEnabled ? messagesChange : undefined}
                changeLabel={analyticsEnabled ? "son 7 gün" : undefined}
                icon={MessageSquare}
                color="bg-gradient-to-br from-blue-500 to-cyan-500"
              />
              <StatCard
                title="Toplam Konuşma"
                value={stats?.totals.conversations || 0}
                change={analyticsEnabled ? conversationsChange : undefined}
                changeLabel={analyticsEnabled ? "son 7 gün" : undefined}
                icon={Activity}
                color="bg-gradient-to-br from-violet-500 to-purple-500"
              />
              <StatCard
                title="Toplam Lead"
                value={stats?.totals.leads || 0}
                change={analyticsEnabled ? leadsChange : undefined}
                changeLabel={analyticsEnabled ? "son 7 gün" : undefined}
                icon={Users}
                color="bg-gradient-to-br from-green-500 to-emerald-500"
              />
              <StatCard
                title={analyticsEnabled ? "Son 30 Gün AI Yanıt" : "Bugün AI Yanıt"}
                value={analyticsEnabled ? (aiResponses30d || 0) : (stats?.today.ai_responses || 0)}
                icon={Bot}
                color="bg-gradient-to-br from-orange-500 to-amber-500"
              />
            </>
          )}
        </div>

        {/* Charts Row */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Messages Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Mesaj Aktivitesi
              </CardTitle>
              <CardDescription>Son 14 günlük mesaj trafiği</CardDescription>
            </CardHeader>
            <CardContent>
              {analyticsLocked && (
                <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                  Grafikler ücretli planda aktif.
                </div>
              )}
              {analyticsEnabled && (chartLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : (
                <MiniChart data={chartData || []} dataKey="messages_sent" color="bg-blue-500" />
              ))}
              <div className="flex items-center justify-between mt-4 text-sm">
                <span className="text-muted-foreground">Gönderilen Mesajlar</span>
                <span className="font-medium">
                  {analyticsEnabled ? (chartData?.reduce((sum, d) => sum + d.messages_sent, 0) || 0) : (stats?.monthly.messages_sent || 0)} mesaj
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Leads Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PieChart className="w-5 h-5" />
                Lead Yakalama
              </CardTitle>
              <CardDescription>Son 14 günlük lead verileri</CardDescription>
            </CardHeader>
            <CardContent>
              {analyticsLocked && (
                <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                  Lead grafikleri ücretli planda aktif.
                </div>
              )}
              {analyticsEnabled && (chartLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : (
                <MiniChart data={chartData || []} dataKey="leads" color="bg-green-500" />
              ))}
              <div className="flex items-center justify-between mt-4 text-sm">
                <span className="text-muted-foreground">Yakalanan Lead'ler</span>
                <span className="font-medium">
                  {analyticsEnabled ? (chartData?.reduce((sum, d) => sum + d.leads, 0) || 0) : (stats?.monthly.leads_captured || 0)} lead
                </span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Today Stats */}
        <Card>
          <CardHeader>
            <CardTitle>Bugünkü Performans</CardTitle>
            <CardDescription>Günlük aktivite özeti</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                <p className="text-sm text-muted-foreground">Gönderilen</p>
                <p className="text-2xl font-bold">{stats?.today.messages_sent || 0}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                <p className="text-sm text-muted-foreground">Alınan</p>
                <p className="text-2xl font-bold">{stats?.today.messages_received || 0}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                <p className="text-sm text-muted-foreground">AI Yanıt</p>
                <p className="text-2xl font-bold">{stats?.today.ai_responses || 0}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                <p className="text-sm text-muted-foreground">Konuşma</p>
                <p className="text-2xl font-bold">{stats?.today.conversations_started || 0}</p>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                <p className="text-sm text-muted-foreground">Lead</p>
                <p className="text-2xl font-bold">{stats?.today.leads_captured || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Usage Summary */}
        {usageStats && (
          <Card>
            <CardHeader>
              <CardTitle>Kullanım Özeti</CardTitle>
              <CardDescription>Aylık limit ve kullanım durumu</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm">Mesaj Kullanımı</span>
                    <span className="text-sm font-medium">
                      {usageStats.messages_used} / {usageStats.message_limit}
                    </span>
                  </div>
                  <div className="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full transition-all',
                        usageStats.message_usage_percent > 80
                          ? 'bg-red-500'
                          : usageStats.message_usage_percent > 50
                            ? 'bg-amber-500'
                            : 'bg-green-500'
                      )}
                      style={{ width: `${usageStats.message_usage_percent}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {usageStats.messages_remaining} mesaj kaldı
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-4">
                    <p className="text-sm text-muted-foreground">Bugün toplam mesaj</p>
                    <p className="text-xl font-semibold">{todayTotalMessages}</p>
                  </div>
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-4">
                    <p className="text-sm text-muted-foreground">Bu ay toplam mesaj</p>
                    <p className="text-xl font-semibold">{totalMonthlyMessages}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </ContentContainer>
  )
}
