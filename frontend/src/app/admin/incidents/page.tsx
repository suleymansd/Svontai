'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Plus, Filter } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { FilterBar } from '@/components/shared/filter-bar'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { incidentsApi, systemEventsApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

export default function IncidentsPage() {
  const router = useRouter()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [severityFilter, setSeverityFilter] = useState<string | undefined>()
  const [statusFilter, setStatusFilter] = useState<string | undefined>()

  const [form, setForm] = useState({
    title: '',
    severity: 'sev3',
    status: 'open',
    tenant_id: '',
  })

  const { data: incidents, isLoading } = useQuery({
    queryKey: ['incidents', severityFilter, statusFilter],
    queryFn: () => incidentsApi.list({ skip: 0, limit: 50, severity: severityFilter, status: statusFilter }).then(res => res.data),
  })

  const { data: events } = useQuery({
    queryKey: ['system-events-admin'],
    queryFn: () => systemEventsApi.list({ skip: 0, limit: 20 }).then(res => res.data),
  })

  const createMutation = useMutation({
    mutationFn: () => incidentsApi.create({
      title: form.title,
      severity: form.severity,
      status: form.status,
      tenant_id: form.tenant_id || null,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      setIsCreateOpen(false)
      setForm({ title: '', severity: 'sev3', status: 'open', tenant_id: '' })
      toast({ title: 'Incident oluşturuldu' })
    },
  })

  const columns: DataColumn<any>[] = [
    {
      key: 'title',
      header: 'Başlık',
      render: (row) => <span className="font-medium">{row.title}</span>,
    },
    {
      key: 'severity',
      header: 'Seviye',
      render: (row) => <Badge variant="outline">{row.severity}</Badge>,
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => <Badge variant={row.status === 'resolved' ? 'success' : 'secondary'}>{row.status}</Badge>,
    },
    {
      key: 'tenant_id',
      header: 'Tenant',
      render: (row) => <span className="text-xs text-muted-foreground">{row.tenant_id || 'global'}</span>,
    },
  ]

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Incidents"
          description="Sistem genelindeki olayları yönetin."
          actions={(
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Incident Oluştur
            </Button>
          )}
        />

        <FilterBar
          searchPlaceholder="Incident ara..."
          onSearchChange={() => {}}
          actions={(
            <Button variant="outline" size="sm" onClick={() => setSeverityFilter(undefined)}>
              <Filter className="h-4 w-4 mr-2" />
              Filtreleri Temizle
            </Button>
          )}
        />

        <DataTable
          columns={columns}
          data={incidents || []}
          loading={isLoading}
          onRowClick={(row) => router.push(`/admin/incidents/${row.id}`)}
          emptyState={(
            <EmptyState
              icon={<AlertTriangle className="h-6 w-6 text-primary" />}
              title="Incident yok"
              description="Yeni bir incident oluşturabilir veya sistem olaylarını takip edebilirsiniz."
            />
          )}
        />

        <div className="rounded-2xl border border-border/70 bg-card/95 shadow-soft p-5">
          <h3 className="text-sm font-semibold mb-3">Son Sistem Olayları</h3>
          <div className="space-y-3">
            {(events || []).map((event: any) => (
              <div key={event.id} className="flex items-start justify-between gap-4 rounded-xl border border-border/60 bg-muted/30 p-3">
                <div>
                  <p className="text-sm font-medium">{event.code}</p>
                  <p className="text-xs text-muted-foreground">{event.message}</p>
                </div>
                <Badge variant="outline">{event.level}</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>

      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>Incident Oluştur</DialogTitle>
            <DialogDescription>Olay başlığı ve seviyesi belirleyin.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Başlık</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Seviye (sev1-4)</Label>
              <Input value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Durum</Label>
              <Input value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Tenant ID (opsiyonel)</Label>
              <Input value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })} />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>İptal</Button>
            <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
