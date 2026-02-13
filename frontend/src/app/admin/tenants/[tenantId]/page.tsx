'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { Activity, ShieldCheck } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { SectionCard } from '@/components/shared/section-card'
import { MetaRow } from '@/components/shared/meta-row'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'
import { adminApi } from '@/lib/api'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { useToast } from '@/components/ui/use-toast'
import { setAdminTenantContext } from '@/lib/admin-tenant-context'

export default function TenantDetailPage({ params }: { params: { tenantId: string } }) {
  const tenantId = params.tenantId
  const router = useRouter()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [flagInput, setFlagInput] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['admin-tenant', tenantId],
    queryFn: () => adminApi.getTenant(tenantId).then((res) => res.data),
  })

  const suspendMutation = useMutation({
    mutationFn: () => adminApi.suspendTenant(tenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-tenant', tenantId] })
      toast({ title: 'Tenant askıya alındı' })
    },
  })

  const unsuspendMutation = useMutation({
    mutationFn: () => adminApi.unsuspendTenant(tenantId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-tenant', tenantId] })
      toast({ title: 'Tenant aktif' })
    },
  })

  const updateFlagsMutation = useMutation({
    mutationFn: (flags: string[]) => adminApi.updateTenantFeatureFlags(tenantId, flags),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-tenant', tenantId] })
      toast({ title: 'Feature flags güncellendi' })
    },
  })

  const runsColumns: DataColumn<any>[] = [
    { key: 'id', header: 'Run', render: (row) => <span className="font-medium">{row.id}</span> },
    { key: 'status', header: 'Durum', render: (row) => <Badge variant={row.status === 'success' ? 'success' : 'secondary'}>{row.status}</Badge> },
    { key: 'created_at', header: 'Zaman', render: (row) => <span className="text-sm text-muted-foreground">{row.created_at}</span> },
  ]

  const incidentColumns: DataColumn<any>[] = [
    { key: 'title', header: 'Incident', render: (row) => <span className="font-medium">{row.title}</span> },
    { key: 'severity', header: 'Seviye', render: (row) => <Badge variant="outline">{row.severity}</Badge> },
    { key: 'status', header: 'Durum', render: (row) => <Badge variant={row.status === 'resolved' ? 'success' : 'secondary'}>{row.status}</Badge> },
  ]

  const handleOpenCustomerPanel = () => {
    if (!data?.tenant?.id) {
      return
    }
    setAdminTenantContext(data.tenant.id, data.tenant.name)
    toast({ title: 'Tenant context seçildi', description: `${data.tenant.name} müşteri paneli açılıyor.` })
    router.push('/dashboard')
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title={data?.tenant?.name || 'Tenant'}
          description={data?.owner_email || 'Tenant detayları'}
          actions={(
            <Link href="/admin/tenants">
              <Button variant="outline">Geri Dön</Button>
            </Link>
          )}
        />

        <SectionCard
          title="Tenant Profili"
          description="Plan ve özellik durumları"
          actions={<Badge variant="outline">{data?.plan_name || 'Plan yok'}</Badge>}
        >
          <div className="grid gap-3">
            <MetaRow label="Owner" value={data?.owner_name || '-'} />
            <MetaRow label="Owner Email" value={data?.owner_email || '-'} />
            <MetaRow label="Plan" value={data?.plan_name || '-'} />
            <MetaRow label="Feature Flags" value={data?.feature_flags?.join(', ') || '-'} />
          </div>
        </SectionCard>

        <SectionCard title="Tenant Actions" description="Operasyonel kontroller">
          <div className="flex flex-wrap gap-2">
            <Button onClick={handleOpenCustomerPanel}>
              Müşteri Paneline Geç
            </Button>
            <Button variant="outline" onClick={() => suspendMutation.mutate()} disabled={suspendMutation.isPending}>
              Suspend
            </Button>
            <Button variant="outline" onClick={() => unsuspendMutation.mutate()} disabled={unsuspendMutation.isPending}>
              Unsuspend
            </Button>
          </div>
        </SectionCard>

        <SectionCard title="Feature Flags" description="Tenant bazlı özellik yönetimi">
          <div className="flex flex-wrap gap-2">
            {(data?.feature_flags || []).map((flag: string) => (
              <Badge key={flag} variant="outline">{flag}</Badge>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-2">
            <input
              className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm"
              placeholder="Yeni flag ekle (ör. analytics)"
              value={flagInput}
              onChange={(e) => setFlagInput(e.target.value)}
            />
            <Button
              onClick={() => updateFlagsMutation.mutate([...(data?.feature_flags || []), flagInput].filter(Boolean))}
              disabled={!flagInput}
            >
              Ekle
            </Button>
          </div>
        </SectionCard>

        <div className="grid gap-6 lg:grid-cols-2">
          <SectionCard title="Recent Runs" description="Son otomasyon koşumları">
            <DataTable
              columns={runsColumns}
              data={data?.recent_runs || []}
              loading={isLoading}
              emptyState={<EmptyState icon={<Activity className="h-5 w-5 text-primary" />} title="Run yok" />}
            />
          </SectionCard>

          <SectionCard title="Recent Incidents" description="Son incident kayıtları">
            <DataTable
              columns={incidentColumns}
              data={data?.recent_incidents || []}
              loading={isLoading}
              emptyState={<EmptyState icon={<ShieldCheck className="h-5 w-5 text-primary" />} title="Incident yok" />}
            />
          </SectionCard>
        </div>
      </div>
    </ContentContainer>
  )
}
