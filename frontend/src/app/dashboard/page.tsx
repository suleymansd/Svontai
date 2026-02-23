'use client'

import { useQuery } from '@tanstack/react-query'
import {
  Bot,
  BarChart3,
  MessageSquare,
  Users,
  TrendingUp,
  Zap,
  Plus
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { billingApi, botApi, leadApi, conversationApi } from '@/lib/api'
import Link from 'next/link'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

export default function DashboardPage() {
  const { data: bots, isLoading: botsLoading } = useQuery({
    queryKey: ['bots'],
    queryFn: () => botApi.list().then(res => res.data),
  })

  const { data: leads, isLoading: leadsLoading } = useQuery({
    queryKey: ['leads'],
    queryFn: () => leadApi.list({ limit: 100 }).then(res => res.data),
  })
  const { data: billingLimits } = useQuery({
    queryKey: ['billing-limits-widget'],
    queryFn: () => billingApi.getLimits().then(res => res.data),
  })

  const isLoading = botsLoading || leadsLoading

  const activeBots = bots?.filter((bot: any) => bot.is_active).length || 0
  const totalLeads = leads?.length || 0
  const totalBots = bots?.length || 0
  const monthlyUsed = Number(billingLimits?.usage?.monthly_runs_used || 0)
  const monthlyLimit = Number(billingLimits?.limits?.monthly_runs || 0)
  const topTools = Object.entries(billingLimits?.usage?.by_tool || {})
    .sort((a: any, b: any) => Number(b[1]) - Number(a[1]))
    .slice(0, 3)

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Hoş Geldiniz"
          description="İşletmenizin performansını ve müşterilerinizin etkileşimini takip edin."
          icon={<Icon3DBadge icon={Bot} from="from-primary" to="to-violet-500" />}
          actions={(
            <Link href="/dashboard/bots">
              <Button>
                <Plus className="w-4 h-4 mr-2" />
                Yeni Bot Oluştur
              </Button>
            </Link>
          )}
        />

        {/* Stats Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
              <KPIStat label="Toplam Bot" value={totalBots} icon={<Bot className="h-5 w-5" />} />
              <KPIStat label="Aktif Bot" value={activeBots} icon={<Zap className="h-5 w-5" />} />
              <KPIStat label="Toplam Lead" value={totalLeads} icon={<Users className="h-5 w-5" />} />
              <KPIStat label="Yanıt Oranı" value={totalBots > 0 ? '%98.5' : '-'} icon={<TrendingUp className="h-5 w-5" />} />
            </>
          )}
        </div>

        <Card className="border border-border/70 shadow-soft">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Bu Ay Kullanım</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-sm text-muted-foreground">
              {monthlyUsed.toLocaleString('tr-TR')} / {monthlyLimit.toLocaleString('tr-TR')} tool run
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-500 to-violet-500"
                style={{
                  width: `${monthlyLimit > 0 ? Math.min(100, Math.round((monthlyUsed / monthlyLimit) * 100)) : 0}%`,
                }}
              />
            </div>
            <div className="text-xs text-muted-foreground">
              Top 3 tool:{' '}
              {topTools.length > 0
                ? topTools.map(([slug, count]: any) => `${slug} (${count})`).join(', ')
                : 'Henüz kullanım yok'}
            </div>
            <div className="flex items-center gap-2">
              <Link href="/dashboard/tools">
                <Button size="sm" variant="outline">Marketplace</Button>
              </Link>
              <Link href="/dashboard/billing">
                <Button size="sm">Yükselt</Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Bots Overview */}
        <Card className="border border-border/70 shadow-soft gradient-border-animated">
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
              <EmptyState
                icon={<Bot className="h-8 w-8 text-primary" />}
                title="İlk botunuzu oluşturun"
                description="Müşterilerinize 7/24 otomatik yanıt vermek için ilk AI asistanınızı oluşturun."
                action={(
                  <Link href="/dashboard/bots">
                    <Button>
                      <Plus className="w-4 h-4 mr-2" />
                      Bot Oluştur
                    </Button>
                  </Link>
                )}
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {bots?.slice(0, 6).map((bot: any) => (
                  <Link key={bot.id} href={`/dashboard/bots/${bot.id}`}>
                    <div className="p-4 rounded-2xl border border-border/70 hover:border-primary/30 hover:shadow-glow-primary transition-all duration-300 group card-hover-lift gradient-border-animated">
                      <div className="flex items-center gap-3 mb-4">
                        <div
                          className="w-12 h-12 rounded-xl flex items-center justify-center shadow-soft"
                          style={{ backgroundColor: bot.primary_color + '20' }}
                        >
                          <Bot className="w-6 h-6" style={{ color: bot.primary_color }} />
                        </div>
                        <div>
                          <h4 className="font-semibold group-hover:text-primary transition-colors">{bot.name}</h4>
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
        <div className="grid gap-4 md:grid-cols-3">
          <Link href="/dashboard/bots">
            <Card className="border border-border/70 hover:shadow-glow-primary transition-all duration-300 cursor-pointer group card-hover-lift gradient-border-animated">
              <CardContent className="p-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 flex items-center justify-center group-hover:scale-110 transition-transform shadow-glow-primary">
                    <Bot className="w-6 h-6 text-primary" />
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
            <Card className="border border-border/70 hover:shadow-glow-primary transition-all duration-300 cursor-pointer group card-hover-lift gradient-border-animated">
              <CardContent className="p-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-success/15 to-success/5 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Users className="w-6 h-6 text-success" />
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
            <Card className="border border-border/70 hover:shadow-glow-primary transition-all duration-300 cursor-pointer group card-hover-lift gradient-border-animated">
              <CardContent className="p-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-info/15 to-info/5 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <MessageSquare className="w-6 h-6 text-info" />
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
    </ContentContainer>
  )
}
