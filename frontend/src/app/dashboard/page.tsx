'use client'

import { useQuery } from '@tanstack/react-query'
import { 
  Bot, 
  MessageSquare, 
  Users, 
  TrendingUp, 
  ArrowUpRight, 
  ArrowDownRight,
  Clock,
  Zap,
  Plus
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { botApi, leadApi, conversationApi } from '@/lib/api'
import Link from 'next/link'
import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string | number
  icon: React.ElementType
  trend?: { value: number; label: string }
  color: string
  delay?: number
}

function StatCard({ title, value, icon: Icon, trend, color, delay = 0 }: StatCardProps) {
  const isPositive = trend && trend.value >= 0

  return (
    <Card className="relative overflow-hidden card-hover animate-fade-in-up" style={{ animationDelay: `${delay}ms` }}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground mb-1">{title}</p>
            <p className="text-3xl font-bold">{value}</p>
            {trend && (
              <div className={cn(
                'flex items-center gap-1 mt-2 text-sm',
                isPositive ? 'text-green-600' : 'text-red-600'
              )}>
                {isPositive ? (
                  <ArrowUpRight className="w-4 h-4" />
                ) : (
                  <ArrowDownRight className="w-4 h-4" />
                )}
                <span className="font-medium">{Math.abs(trend.value)}%</span>
                <span className="text-muted-foreground">{trend.label}</span>
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
      {/* Decorative gradient */}
      <div className={cn(
        'absolute bottom-0 left-0 right-0 h-1',
        color.replace('bg-gradient-to-br', 'bg-gradient-to-r')
      )} />
    </Card>
  )
}

export default function DashboardPage() {
  const { data: bots, isLoading: botsLoading } = useQuery({
    queryKey: ['bots'],
    queryFn: () => botApi.list().then(res => res.data),
  })

  const { data: leads, isLoading: leadsLoading } = useQuery({
    queryKey: ['leads'],
    queryFn: () => leadApi.list({ limit: 100 }).then(res => res.data),
  })

  const isLoading = botsLoading || leadsLoading

  const activeBots = bots?.filter((bot: any) => bot.is_active).length || 0
  const totalLeads = leads?.length || 0
  const totalBots = bots?.length || 0

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Hoş Geldiniz! 👋</h1>
          <p className="text-muted-foreground mt-1">İşletmenizin performansını takip edin</p>
        </div>
        <Link href="/dashboard/bots">
          <Button className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 shadow-lg shadow-blue-500/25">
            <Plus className="w-4 h-4 mr-2" />
            Yeni Bot Oluştur
          </Button>
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          [...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-8 w-16" />
                    <Skeleton className="h-4 w-32" />
                  </div>
                  <Skeleton className="h-12 w-12 rounded-2xl" />
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          <>
            <StatCard
              title="Toplam Bot"
              value={totalBots}
              icon={Bot}
              color="bg-gradient-to-br from-blue-500 to-cyan-500"
              delay={0}
            />
            <StatCard
              title="Aktif Bot"
              value={activeBots}
              icon={Zap}
              color="bg-gradient-to-br from-violet-500 to-purple-500"
              delay={100}
            />
            <StatCard
              title="Toplam Lead"
              value={totalLeads}
              icon={Users}
              color="bg-gradient-to-br from-green-500 to-emerald-500"
              delay={200}
            />
            <StatCard
              title="Yanıt Oranı"
              value={totalBots > 0 ? "%98.5" : "-"}
              icon={TrendingUp}
              color="bg-gradient-to-br from-orange-500 to-amber-500"
              delay={300}
            />
          </>
        )}
      </div>

      {/* Bots Overview */}
      <Card className="animate-fade-in-up" style={{ animationDelay: '400ms' }}>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Botlarınız</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">{activeBots} aktif, {totalBots - activeBots} pasif</p>
          </div>
          <Link href="/dashboard/bots">
            <Button variant="outline">
              Tümünü Yönet
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="p-4 rounded-2xl border">
                  <div className="flex items-center gap-3 mb-4">
                    <Skeleton className="w-12 h-12 rounded-xl" />
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-3 w-16" />
                    </div>
                  </div>
                  <Skeleton className="h-2 w-full rounded-full" />
                </div>
              ))}
            </div>
          ) : bots?.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-100 to-violet-100 dark:from-blue-900/30 dark:to-violet-900/30 flex items-center justify-center mb-4">
                <Bot className="w-10 h-10 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold mb-2">İlk botunuzu oluşturun</h3>
              <p className="text-muted-foreground max-w-sm mb-6">
                Müşterilerinize 7/24 otomatik yanıt vermek için ilk AI asistanınızı oluşturun.
              </p>
              <Link href="/dashboard/bots">
                <Button className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700">
                  <Plus className="w-4 h-4 mr-2" />
                  Bot Oluştur
                </Button>
              </Link>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {bots?.slice(0, 6).map((bot: any) => (
                <Link key={bot.id} href={`/dashboard/bots/${bot.id}`}>
                  <div className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-lg transition-all duration-300 group">
                    <div className="flex items-center gap-3 mb-4">
                      <div 
                        className="w-12 h-12 rounded-xl flex items-center justify-center shadow-lg"
                        style={{ backgroundColor: bot.primary_color + '20' }}
                      >
                        <Bot className="w-6 h-6" style={{ color: bot.primary_color }} />
                      </div>
                      <div>
                        <h4 className="font-semibold group-hover:text-blue-600 transition-colors">{bot.name}</h4>
                        <Badge variant={bot.is_active ? 'success' : 'secondary'} className="text-xs">
                          {bot.is_active ? 'Aktif' : 'Pasif'}
                        </Badge>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {bot.description || 'Açıklama eklenmemiş'}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid gap-6 md:grid-cols-3">
        <Link href="/dashboard/bots">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Bot className="w-6 h-6 text-blue-600" />
                </div>
                <div>
                  <h3 className="font-semibold">Bot Yönetimi</h3>
                  <p className="text-sm text-muted-foreground">Botları düzenle ve eğit</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>

        <Link href="/dashboard/leads">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Users className="w-6 h-6 text-green-600" />
                </div>
                <div>
                  <h3 className="font-semibold">Lead'ler</h3>
                  <p className="text-sm text-muted-foreground">Potansiyel müşteriler</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>

        <Link href="/dashboard/conversations">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <MessageSquare className="w-6 h-6 text-violet-600" />
                </div>
                <div>
                  <h3 className="font-semibold">Konuşmalar</h3>
                  <p className="text-sm text-muted-foreground">Müşteri mesajları</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  )
}
