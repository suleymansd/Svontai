'use client'

import { useQuery } from '@tanstack/react-query'
import { 
  MessageSquare, 
  Users, 
  TrendingUp, 
  Bot,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  BarChart3,
  PieChart,
  Calendar,
  Loader2,
  Lock
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { analyticsApi, subscriptionApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import Link from 'next/link'

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
    <Card>
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
            'w-12 h-12 rounded-2xl flex items-center justify-center',
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
            className={cn('flex-1 rounded-t transition-all', color)}
            style={{ height: `${Math.max(height, 5)}%` }}
            title={`${point.date}: ${point[dataKey]}`}
          />
        )
      })}
    </div>
  )
}

export default function AnalyticsPage() {
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: () => analyticsApi.getDashboardStats().then(res => res.data),
  })
  
  const { data: chartData, isLoading: chartLoading } = useQuery<ChartDataPoint[]>({
    queryKey: ['chart-data'],
    queryFn: () => analyticsApi.getChartData(30).then(res => res.data),
  })
  
  const { data: usageStats } = useQuery({
    queryKey: ['usage-stats'],
    queryFn: () => subscriptionApi.getUsageStats().then(res => res.data),
  })
  
  const hasAnalyticsFeature = usageStats?.features?.analytics !== false
  
  if (!hasAnalyticsFeature) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card className="border-amber-200 dark:border-amber-800">
          <CardContent className="p-12 text-center">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
              <Lock className="w-10 h-10 text-amber-600" />
            </div>
            <h2 className="text-2xl font-bold mb-2">Analitik Özellikleri</h2>
            <p className="text-muted-foreground mb-6">
              Detaylı analitikler ve grafikler için planınızı yükseltin.
            </p>
            <Link href="/dashboard/billing">
              <Button className="bg-gradient-to-r from-amber-600 to-orange-600">
                Planları Görüntüle
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }
  
  const isLoading = statsLoading || chartLoading
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Analitikler 📊</h1>
          <p className="text-muted-foreground mt-1">
            İşletmenizin performansını detaylı inceleyin
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="gap-1">
            <Calendar className="w-3 h-3" />
            Son 30 Gün
          </Badge>
        </div>
      </div>
      
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
              title="Toplam Mesaj"
              value={stats?.monthly.messages_sent || 0}
              change={12}
              changeLabel="bu ay"
              icon={MessageSquare}
              color="bg-gradient-to-br from-blue-500 to-cyan-500"
            />
            <StatCard
              title="Konuşma"
              value={stats?.totals.conversations || 0}
              change={8}
              changeLabel="bu ay"
              icon={Activity}
              color="bg-gradient-to-br from-violet-500 to-purple-500"
            />
            <StatCard
              title="Lead"
              value={stats?.totals.leads || 0}
              change={15}
              changeLabel="bu ay"
              icon={Users}
              color="bg-gradient-to-br from-green-500 to-emerald-500"
            />
            <StatCard
              title="AI Yanıt"
              value={stats?.monthly.messages_sent || 0}
              change={10}
              changeLabel="bu ay"
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
            {chartLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <MiniChart 
                data={chartData || []} 
                dataKey="messages_sent" 
                color="bg-blue-500"
              />
            )}
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-muted-foreground">Gönderilen Mesajlar</span>
              <span className="font-medium">
                {chartData?.reduce((sum, d) => sum + d.messages_sent, 0) || 0} mesaj
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
            {chartLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <MiniChart 
                data={chartData || []} 
                dataKey="leads" 
                color="bg-green-500"
              />
            )}
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-muted-foreground">Yakalanan Lead'ler</span>
              <span className="font-medium">
                {chartData?.reduce((sum, d) => sum + d.leads, 0) || 0} lead
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
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

