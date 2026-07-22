'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Building2, CheckCircle2, FlaskConical, LifeBuoy, Loader2, PlayCircle, Rocket, ShieldCheck, UserCheck } from 'lucide-react'
import { adminApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'

const stageLabel: Record<string, string> = {
  concierge: 'Concierge',
  blocked_by_user: 'İzin Bekliyor',
  ready_to_launch: 'Yayına Hazır',
  needs_attention: 'Dikkat',
}

export default function LaunchBoardPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [editingTenantId, setEditingTenantId] = useState<string | null>(null)
  const [profileForm, setProfileForm] = useState({
    industry: 'service',
    tone: 'professional',
    summary: '',
    services: '',
  })
  const launchQuery = useQuery({
    queryKey: ['admin-launch-board'],
    queryFn: () => adminApi.getLaunchBoard({ limit: 200 }).then(res => res.data),
  })

  const data = launchQuery.data
  const items = data?.items || []
  const refreshLaunchBoard = () => queryClient.invalidateQueries({ queryKey: ['admin-launch-board'] })

  const conciergeMutation = useMutation({
    mutationFn: ({ tenantId, status }: { tenantId: string; status: 'pending' | 'in_progress' | 'ready_for_review' | 'launched' | 'blocked' }) =>
      adminApi.updateLaunchConcierge(tenantId, { status, create_ticket: true }),
    onSuccess: () => {
      refreshLaunchBoard()
      toast({ title: 'Durum güncellendi', description: 'Concierge operasyon durumu kaydedildi.' })
    },
  })

  const profileMutation = useMutation({
    mutationFn: (tenantId: string) => adminApi.updateTenantBusinessProfile(tenantId, {
      industry: profileForm.industry,
      tone: profileForm.tone,
      summary: profileForm.summary,
      services: profileForm.services.split(',').map(item => item.trim()).filter(Boolean),
      status: 'ready',
    }),
    onSuccess: () => {
      setEditingTenantId(null)
      refreshLaunchBoard()
      toast({ title: 'Bilgi formasyonu kaydedildi', description: 'Profil bot bilgisine senkronize edildi.' })
    },
  })

  const autopilotMutation = useMutation({
    mutationFn: (tenantId: string) => adminApi.runTenantAutopilot(tenantId),
    onSuccess: () => {
      refreshLaunchBoard()
      toast({ title: 'Autopilot çalıştı', description: 'Bot ve sağlık kontrolleri yenilendi.' })
    },
  })

  const verificationMutation = useMutation({
    mutationFn: (tenantId: string) => adminApi.runTenantVerification(tenantId),
    onSuccess: (response) => {
      refreshLaunchBoard()
      const result = response.data
      toast({
        title: result.ready_for_launch ? 'Satış öncesi test başarılı' : 'Kritik kontroller eksik',
        description: result.summary,
        variant: result.ready_for_launch ? 'default' : 'destructive',
      })
    },
  })

  const launchMutation = useMutation({
    mutationFn: (tenantId: string) => adminApi.launchTenant(tenantId),
    onSuccess: () => {
      refreshLaunchBoard()
      toast({ title: 'Müşteri yayına alındı', description: 'Concierge durumu launched olarak işaretlendi.' })
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      toast({
        title: 'Yayına alma durduruldu',
        description: detail?.message || 'Önce kritik sistem kontrollerini tamamlayın.',
        variant: 'destructive',
      })
    },
  })

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Customer Launch Board"
          description="Yeni müşterilerin bilgi formasyonu, izinleri, bot hazırlığı ve yayına alma durumunu yönetin."
          icon={<Rocket className="h-7 w-7 text-primary" />}
        />

        {launchQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="grid gap-4 md:grid-cols-4">
            <KPIStat label="Toplam Müşteri" value={data?.total || 0} icon={<Building2 className="h-5 w-5" />} />
            <KPIStat label="Concierge Bekleyen" value={data?.pending_concierge || 0} icon={<UserCheck className="h-5 w-5" />} />
            <KPIStat label="İzin Bekleyen" value={data?.blocked_by_user || 0} icon={<AlertTriangle className="h-5 w-5" />} />
            <KPIStat label="Yayına Hazır" value={data?.ready_to_launch || 0} icon={<CheckCircle2 className="h-5 w-5" />} />
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Launch Pipeline</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {launchQuery.isLoading ? (
              <>
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-24 w-full" />
              </>
            ) : items.length === 0 ? (
              <p className="text-sm text-muted-foreground">Henüz launch kaydı yok.</p>
            ) : (
              items.map((item: any) => (
                <div key={item.tenant_id} className="rounded-lg border p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold">{item.tenant_name}</h3>
                        <Badge variant={item.launch_stage === 'ready_to_launch' ? 'success' : item.launch_stage === 'blocked_by_user' ? 'warning' : 'secondary'}>
                          {stageLabel[item.launch_stage] || item.launch_stage}
                        </Badge>
                        <Badge variant={item.setup_mode === 'self_serve' ? 'outline' : 'secondary'}>
                          {item.setup_mode === 'self_serve' ? 'Hızlı Kurulum' : 'Biz Kuralım'}
                        </Badge>
                        <Badge variant={item.whatsapp_status === 'connected' ? 'success' : 'outline'}>
                          WhatsApp: {item.whatsapp_status === 'connected' ? 'bağlı' : 'eksik'}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {item.owner_name} · {item.owner_email} · {item.plan_name || 'Plansız'}
                      </p>
                      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>Sağlık: {item.health_score}/100</span>
                        <span>Bot: {item.bot_count}</span>
                        <span>Ticket: {item.open_tickets}</span>
                        <span>Incident: {item.open_incidents}</span>
                        <span>Profil: {item.business_profile_status}</span>
                      </div>
                      {item.required_user_actions?.length > 0 ? (
                        <p className="text-sm text-amber-600">
                          Kullanıcı izni bekleniyor: {item.required_user_actions.join(', ')}
                        </p>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          Kullanıcıdan bekleyen izin yok; şirket içi bilgi formasyonu yürütülebilir.
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={verificationMutation.isPending}
                        onClick={() => verificationMutation.mutate(item.tenant_id)}
                      >
                        {verificationMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FlaskConical className="mr-2 h-4 w-4" />}
                        Satış Testi
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={conciergeMutation.isPending}
                        onClick={() => conciergeMutation.mutate({ tenantId: item.tenant_id, status: 'in_progress' })}
                      >
                        İşleme Al
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={autopilotMutation.isPending}
                        onClick={() => autopilotMutation.mutate(item.tenant_id)}
                      >
                        {autopilotMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                        Autopilot
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setEditingTenantId(editingTenantId === item.tenant_id ? null : item.tenant_id)
                          setProfileForm({
                            industry: 'service',
                            tone: 'professional',
                            summary: '',
                            services: '',
                          })
                        }}
                      >
                        Bilgi Formasyonu
                      </Button>
                      <Button
                        size="sm"
                        disabled={launchMutation.isPending}
                        onClick={() => launchMutation.mutate(item.tenant_id)}
                      >
                        Yayına Al
                      </Button>
                      {item.concierge_ticket_id ? (
                        <Button asChild variant="outline" size="sm">
                          <Link href={`/admin/tickets/${item.concierge_ticket_id}`}>
                            <LifeBuoy className="mr-2 h-4 w-4" />
                            Concierge Ticket
                          </Link>
                        </Button>
                      ) : null}
                      <Button asChild variant="outline" size="sm">
                        <Link href={`/admin/tenants/${item.tenant_id}`}>
                          <ShieldCheck className="mr-2 h-4 w-4" />
                          Tenant
                        </Link>
                      </Button>
                    </div>
                  </div>
                  {editingTenantId === item.tenant_id ? (
                    <div className="mt-4 rounded-lg border bg-muted/20 p-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <Label>Sektör</Label>
                          <Input value={profileForm.industry} onChange={(event) => setProfileForm({ ...profileForm, industry: event.target.value })} />
                        </div>
                        <div className="space-y-2">
                          <Label>Ton</Label>
                          <Input value={profileForm.tone} onChange={(event) => setProfileForm({ ...profileForm, tone: event.target.value })} />
                        </div>
                      </div>
                      <div className="mt-4 space-y-2">
                        <Label>İşletme özeti</Label>
                        <Textarea value={profileForm.summary} onChange={(event) => setProfileForm({ ...profileForm, summary: event.target.value })} placeholder="Hizmetler, hedef müşteri, sık sorulan konular..." />
                      </div>
                      <div className="mt-4 space-y-2">
                        <Label>Hizmetler</Label>
                        <Input value={profileForm.services} onChange={(event) => setProfileForm({ ...profileForm, services: event.target.value })} placeholder="Virgülle ayırın" />
                      </div>
                      <div className="mt-4 flex gap-2">
                        <Button disabled={profileMutation.isPending || !profileForm.summary.trim()} onClick={() => profileMutation.mutate(item.tenant_id)}>
                          {profileMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                          Kaydet ve Hazır Yap
                        </Button>
                        <Button variant="outline" onClick={() => setEditingTenantId(null)}>Vazgeç</Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </ContentContainer>
  )
}
