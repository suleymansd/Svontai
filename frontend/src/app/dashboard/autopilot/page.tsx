'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, RefreshCw, ShieldCheck, UserCheck, Wrench } from 'lucide-react'
import { autopilotApi, integrationsApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/components/ui/use-toast'

export default function AutopilotPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const statusQuery = useQuery({
    queryKey: ['autopilot-status'],
    queryFn: () => autopilotApi.getStatus().then((res) => res.data),
  })
  const diagnosticsQuery = useQuery({
    queryKey: ['integration-diagnostics'],
    queryFn: () => integrationsApi.getDiagnostics().then((res) => res.data),
  })
  const runMutation = useMutation({
    mutationFn: () => autopilotApi.run().then((res) => res.data),
    onSuccess: () => {
      toast({ title: 'Otonom kurulum çalıştı', description: 'Güvenli otomatik kontroller tamamlandı.' })
      queryClient.invalidateQueries({ queryKey: ['autopilot-status'] })
      queryClient.invalidateQueries({ queryKey: ['integration-diagnostics'] })
    },
  })
  const repairMutation = useMutation({
    mutationFn: (provider: string) => integrationsApi.repair(provider).then((res) => res.data),
    onSuccess: (data) => {
      toast({ title: 'Tanılama tamamlandı', description: data?.message || 'Entegrasyon kontrol edildi.' })
      queryClient.invalidateQueries({ queryKey: ['autopilot-status'] })
      queryClient.invalidateQueries({ queryKey: ['integration-diagnostics'] })
    },
  })

  const status = statusQuery.data
  const diagnostics = diagnosticsQuery.data?.items || status?.diagnostics || []
  const healthScore = Number(status?.health_score || diagnosticsQuery.data?.health_score || 0)
  const requiredActions = status?.required_user_actions || []
  const concierge = status?.concierge_enrichment
  const businessProfile = status?.business_profile

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Otonom Kurulum Merkezi"
          description="Sistem kurulum, entegrasyon sağlığı ve güvenli otomatik onarım durumunu buradan yönetir."
          icon={<ShieldCheck className="h-7 w-7 text-primary" />}
          actions={(
            <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
              <RefreshCw className="mr-2 h-4 w-4" />
              {runMutation.isPending ? 'Çalışıyor...' : 'Autopilot Çalıştır'}
            </Button>
          )}
        />

        {statusQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            <KPIStat label="Sağlık Skoru" value={`${healthScore}/100`} icon={<ShieldCheck className="h-5 w-5" />} />
            <KPIStat label="Durum" value={status?.status === 'ready' ? 'Hazır' : 'Dikkat'} icon={<CheckCircle2 className="h-5 w-5" />} />
            <KPIStat label="Bilgi Formasyonu" value={businessProfile?.status === 'ready' ? 'Hazır' : 'Bizde'} icon={<UserCheck className="h-5 w-5" />} />
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Şirket Tarafından Hazırlanan Bilgi Formasyonu</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-medium">
                  {businessProfile?.status === 'ready'
                    ? 'İşletme profiliniz bot tarafından kullanılmaya hazır.'
                    : 'Ekibimiz işletme bilginizi bot için hazırlıyor.'}
                </p>
                <p className="text-sm text-muted-foreground">
                  Kullanıcıdan uzun form beklenmez. SmartWA bu sırada güvenli varsayılan bilgiyle çalışır; ekibimiz profilinizi işlediğinde bot yanıtları otomatik daha özel hale gelir.
                </p>
              </div>
              <Badge variant={businessProfile?.status === 'ready' ? 'success' : 'secondary'}>
                {concierge?.status || businessProfile?.status || 'otomatik'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Gerekli Kullanıcı Aksiyonları</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {requiredActions.length === 0 ? (
              <p className="text-sm text-muted-foreground">Kullanıcı onayı gerektiren açık aksiyon yok.</p>
            ) : (
              requiredActions.map((action: any) => (
                <div key={action.key} className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium">{action.label}</p>
                    <p className="text-sm text-muted-foreground">{action.url || 'Panel aksiyonu gerekli'}</p>
                  </div>
                  {action.url && (
                    <Button asChild variant="outline">
                      <a href={action.url}>Aç</a>
                    </Button>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Entegrasyon Tanılamaları</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            {diagnostics.map((item: any) => (
              <div key={item.provider} className="rounded-lg border p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium capitalize">{item.provider}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{item.message}</p>
                  </div>
                  <Badge variant={item.status === 'connected' ? 'success' : item.requires_user_action ? 'warning' : 'secondary'}>
                    {item.status}
                  </Badge>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Skor: {item.health_score}/100</span>
                  <Button size="sm" variant="outline" onClick={() => repairMutation.mutate(item.provider)} disabled={repairMutation.isPending}>
                    <Wrench className="mr-2 h-4 w-4" />
                    Kontrol Et
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </ContentContainer>
  )
}
