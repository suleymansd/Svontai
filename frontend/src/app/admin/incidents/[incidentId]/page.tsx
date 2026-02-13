'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, BadgeCheck, CalendarClock, ShieldAlert } from 'lucide-react'
import { incidentsApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { SectionCard } from '@/components/shared/section-card'
import { MetaRow } from '@/components/shared/meta-row'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'

interface Incident {
  id: string
  tenant_id?: string | null
  title: string
  severity: string
  status: string
  assigned_to?: string | null
  root_cause?: string | null
  resolution?: string | null
  created_at: string
  updated_at: string
}

export default function IncidentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const incidentId = params.incidentId as string

  const { data: incident, isLoading } = useQuery<Incident>({
    queryKey: ['incident', incidentId],
    queryFn: () => incidentsApi.get(incidentId).then(res => res.data),
    enabled: Boolean(incidentId),
  })

  const [form, setForm] = useState({
    title: '',
    severity: 'sev3',
    status: 'open',
    assigned_to: '',
    root_cause: '',
    resolution: '',
  })

  useEffect(() => {
    if (!incident) return
    setForm({
      title: incident.title,
      severity: incident.severity,
      status: incident.status,
      assigned_to: incident.assigned_to || '',
      root_cause: incident.root_cause || '',
      resolution: incident.resolution || '',
    })
  }, [incident])

  const updateMutation = useMutation({
    mutationFn: () => incidentsApi.update(incidentId, {
      title: form.title,
      severity: form.severity,
      status: form.status,
      assigned_to: form.assigned_to || null,
      root_cause: form.root_cause || null,
      resolution: form.resolution || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incident', incidentId] })
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      toast({ title: 'Incident güncellendi' })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Incident güncellenemedi',
        variant: 'destructive',
      })
    },
  })

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title={incident?.title || 'Incident Detayı'}
          description="Olayın kök nedeni, çözüm ve durum güncellemelerini yönetin."
          actions={(
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => router.push('/admin/incidents')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Geri Dön
              </Button>
              <Button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending}>
                <BadgeCheck className="h-4 w-4 mr-2" />
                Kaydet
              </Button>
            </div>
          )}
        />

        {isLoading && (
          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <SectionCard title="Incident Özeti" description="Yükleniyor...">
              <div className="space-y-4">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-1/3" />
              </div>
            </SectionCard>
            <SectionCard title="Metadata">
              <div className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
              </div>
            </SectionCard>
          </div>
        )}

        {!isLoading && incident && (
          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <SectionCard title="Incident Özeti" description="Durum ve kök neden bilgilerini güncelleyin.">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label>Başlık</Label>
                  <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>Seviye</Label>
                  <Input value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>Durum</Label>
                  <Input value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label>Atanan kullanıcı ID</Label>
                  <Input value={form.assigned_to} onChange={(e) => setForm({ ...form, assigned_to: e.target.value })} />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label>Kök neden</Label>
                  <Textarea rows={4} value={form.root_cause} onChange={(e) => setForm({ ...form, root_cause: e.target.value })} />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label>Çözüm</Label>
                  <Textarea rows={4} value={form.resolution} onChange={(e) => setForm({ ...form, resolution: e.target.value })} />
                </div>
              </div>
            </SectionCard>

            <div className="space-y-6">
              <SectionCard title="Metadata" description="Olay meta bilgileri.">
                <div className="space-y-3">
                  <MetaRow label="ID" value={incident.id} />
                  <MetaRow label="Tenant" value={incident.tenant_id || 'global'} />
                  <MetaRow label="Oluşturma" value={new Date(incident.created_at).toLocaleString('tr-TR')} />
                  <MetaRow label="Güncelleme" value={new Date(incident.updated_at).toLocaleString('tr-TR')} />
                </div>
              </SectionCard>

              <SectionCard title="Durum" description="Mevcut incident seviyesi ve durumu.">
                <div className="flex flex-wrap items-center gap-3">
                  <Badge variant="outline" className="gap-2">
                    <ShieldAlert className="h-4 w-4" />
                    {incident.severity}
                  </Badge>
                  <Badge variant={incident.status === 'resolved' ? 'success' : 'secondary'}>
                    {incident.status}
                  </Badge>
                  <Badge variant="outline" className="gap-2">
                    <CalendarClock className="h-4 w-4" />
                    {new Date(incident.updated_at).toLocaleDateString('tr-TR')}
                  </Badge>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  İyileştirme aksiyonlarını yazdıktan sonra durumu güncellemeyi unutmayın.
                </p>
              </SectionCard>
            </div>
          </div>
        )}
      </div>
    </ContentContainer>
  )
}
