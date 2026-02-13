'use client'

import { useState, useEffect } from 'react'
import {
  Users,
  Building2,
  Bot,
  MessageSquare,
  TrendingUp,
  UserPlus,
  Activity,
  Zap,
} from 'lucide-react'
import { adminApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { systemEventsApi } from '@/lib/api'
import { SectionCard } from '@/components/shared/section-card'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'

interface AdminStats {
  total_users: number
  active_users: number
  total_tenants: number
  total_bots: number
  active_bots: number
  total_conversations: number
  total_messages: number
  total_leads: number
  new_users_today: number
  new_users_week: number
  messages_today: number
  messages_week: number
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState<any[]>([])
  const [errors, setErrors] = useState<any[]>([])

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await adminApi.getStats()
        setStats(response.data)
        const eventsResponse = await systemEventsApi.list({ skip: 0, limit: 10 })
        setEvents(eventsResponse.data)
        const errorsResponse = await systemEventsApi.list({ skip: 0, limit: 5, level: 'error' })
        setErrors(errorsResponse.data)
      } catch (error) {
        console.error('Failed to fetch stats:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [])

  if (loading) {
    return (
      <ContentContainer>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
        </div>
      </ContentContainer>
    )
  }

  const statCards = [
    { label: 'Toplam Kullanıcı', value: stats?.total_users || 0, icon: Users },
    { label: 'Aktif Kullanıcı', value: stats?.active_users || 0, icon: UserPlus },
    { label: 'Tenant', value: stats?.total_tenants || 0, icon: Building2 },
    { label: 'Bot', value: stats?.total_bots || 0, icon: Bot },
    { label: 'Aktif Bot', value: stats?.active_bots || 0, icon: Zap },
    { label: 'Konuşma', value: stats?.total_conversations || 0, icon: MessageSquare },
    { label: 'Mesaj', value: stats?.total_messages || 0, icon: Activity },
    { label: 'Lead', value: stats?.total_leads || 0, icon: TrendingUp },
  ]

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Admin Dashboard"
          description="Sistem genel görünümü ve metrikler."
        />

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {statCards.map((stat) => (
            <KPIStat
              key={stat.label}
              label={stat.label}
              value={stat.value}
              icon={<stat.icon className="h-5 w-5" />}
            />
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <SectionCard title="Today's Failures" description="Son 5 kritik hata">
            {errors.length === 0 ? (
              <EmptyState title="Hata yok" description="Bugün kritik hata kaydı bulunmuyor." />
            ) : (
              <div className="space-y-3">
                {errors.map((event) => (
                  <div key={event.id} className="flex items-start justify-between gap-3 rounded-xl border border-border/70 bg-muted/30 p-3">
                    <div>
                      <p className="text-sm font-medium">{event.code}</p>
                      <p className="text-xs text-muted-foreground">{event.message}</p>
                    </div>
                    <Badge variant="destructive">{event.level}</Badge>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard title="Latest Events" description="Sistem genelindeki son olaylar">
            {events.length === 0 ? (
              <EmptyState title="Event yok" description="Henüz sistem olayı kaydı bulunmuyor." />
            ) : (
              <div className="space-y-3">
                {events.map((event) => (
                  <div key={event.id} className="flex items-start justify-between gap-3 rounded-xl border border-border/70 bg-muted/30 p-3">
                    <div>
                      <p className="text-sm font-medium">{event.code}</p>
                      <p className="text-xs text-muted-foreground">{event.message}</p>
                    </div>
                    <Badge variant="outline">{event.source}</Badge>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </ContentContainer>
  )
}
