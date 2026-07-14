'use client'

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, Building2 } from 'lucide-react'
import { agencyApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

export default function AgencyClientHealthPage() {
  const params = useParams<{ tenantId: string }>()
  const healthQuery = useQuery({
    queryKey: ['agency-client-health', params.tenantId],
    queryFn: () => agencyApi.getClientHealth(params.tenantId).then((res) => res.data),
    enabled: Boolean(params.tenantId),
  })

  const payload = healthQuery.data
  const client = payload?.client
  const autopilot = payload?.autopilot

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title={client?.name || 'Müşteri Sağlığı'}
          description="Ajans müşterisi için otonom kurulum, entegrasyon ve operasyon görünümü."
          icon={<Building2 className="h-7 w-7 text-primary" />}
        />

        {healthQuery.isLoading ? (
          <Skeleton className="h-56 w-full" />
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm text-muted-foreground">Sağlık Skoru</p>
                  <p className="mt-2 text-3xl font-semibold">{autopilot?.health_score || 0}/100</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm text-muted-foreground">Açık Ticket</p>
                  <p className="mt-2 text-3xl font-semibold">{payload?.open_tickets || 0}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <p className="text-sm text-muted-foreground">Açık Incident</p>
                  <p className="mt-2 text-3xl font-semibold">{payload?.open_incidents || 0}</p>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Gerekli Aksiyonlar</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(autopilot?.required_user_actions || []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">Açık aksiyon yok.</p>
                ) : (
                  autopilot.required_user_actions.map((action: any) => (
                    <div key={action.key} className="flex items-center gap-3 rounded-lg border p-3">
                      <AlertTriangle className="h-4 w-4 text-warning" />
                      <span className="text-sm">{action.label}</span>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Son Otomasyon Runları</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(payload?.recent_runs || []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">Henüz run yok.</p>
                ) : (
                  payload.recent_runs.map((run: any) => (
                    <div key={run.id} className="flex items-center justify-between rounded-lg border p-3">
                      <div className="flex items-center gap-3">
                        <Activity className="h-4 w-4 text-primary" />
                        <span className="text-sm">{run.channel}</span>
                      </div>
                      <Badge variant={run.status === 'success' ? 'success' : run.status === 'failed' ? 'destructive' : 'secondary'}>
                        {run.status}
                      </Badge>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </ContentContainer>
  )
}
