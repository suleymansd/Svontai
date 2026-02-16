'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LifeBuoy, Plus, Filter, MessageSquareWarning } from 'lucide-react'
import { ticketsApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { FilterBar } from '@/components/shared/filter-bar'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getApiErrorMessage } from '@/lib/api-error'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { cn } from '@/lib/utils'

interface Ticket {
  id: string
  subject: string
  status: string
  priority: string
  created_at: string
  last_activity_at: string
}

export default function TicketsPage() {
  const router = useRouter()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('open')
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [formErrors, setFormErrors] = useState<{ subject?: string; message?: string }>({})
  const [form, setForm] = useState({
    subject: '',
    priority: 'normal',
    message: '',
  })

  const { data: tickets, isLoading } = useQuery<Ticket[]>({
    queryKey: ['tickets', statusFilter],
    queryFn: () => ticketsApi.list({ skip: 0, limit: 50, status: statusFilter }).then(res => res.data),
  })

  const createMutation = useMutation({
    mutationFn: () => ticketsApi.create(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
      setIsCreateOpen(false)
      setFormErrors({})
      setForm({ subject: '', priority: 'normal', message: '' })
      toast({ title: 'Ticket oluşturuldu' })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: getApiErrorMessage(error, 'Ticket oluşturulamadı'),
        variant: 'destructive',
      })
    },
  })

  const columns: DataColumn<Ticket>[] = useMemo(() => [
    {
      key: 'subject',
      header: 'Konu',
      render: (row) => (
        <div className="space-y-1">
          <p className="font-medium">{row.subject}</p>
          <p className="text-xs text-muted-foreground">#{row.id.slice(0, 8)}</p>
        </div>
      ),
    },
    {
      key: 'priority',
      header: 'Öncelik',
      render: (row) => (
        <Badge variant="outline">{row.priority}</Badge>
      ),
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <Badge variant={row.status === 'solved' ? 'success' : row.status === 'pending' ? 'warning' : 'secondary'}>
          {row.status}
        </Badge>
      ),
    },
    {
      key: 'updated',
      header: 'Son aktivite',
      render: (row) => new Date(row.last_activity_at).toLocaleString('tr-TR'),
    },
  ], [])

  const handleCreate = () => {
    const subject = form.subject.trim()
    const message = form.message.trim()
    const nextErrors: { subject?: string; message?: string } = {}

    if (!subject) nextErrors.subject = 'Konu alanı zorunludur.'
    if (!message) nextErrors.message = 'Mesaj alanı zorunludur.'

    if (Object.keys(nextErrors).length > 0) {
      setFormErrors(nextErrors)
      return
    }

    setFormErrors({})
    createMutation.mutate()
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Destek Talepleri"
          description="Ticket'larınızı yönetin ve destek ekibiyle iletişimde kalın."
          icon={<Icon3DBadge icon={LifeBuoy} from="from-cyan-500" to="to-blue-500" />}
          actions={(
            <Button type="button" onClick={() => setIsCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Ticket Oluştur
            </Button>
          )}
        />

        <div className="flex flex-col gap-4">
          <Tabs value={statusFilter} onValueChange={setStatusFilter}>
            <TabsList>
              <TabsTrigger value="open">Açık</TabsTrigger>
              <TabsTrigger value="pending">Beklemede</TabsTrigger>
              <TabsTrigger value="solved">Çözüldü</TabsTrigger>
            </TabsList>
          </Tabs>

          <FilterBar
            searchPlaceholder="Ticket ara..."
            onSearchChange={() => {}}
            actions={(
              <Button variant="outline" size="sm" onClick={() => setStatusFilter('open')}>
                <Filter className="h-4 w-4 mr-2" />
                Filtreleri Sıfırla
              </Button>
            )}
          />
        </div>

        <DataTable
          columns={columns}
          data={tickets || []}
          loading={isLoading}
          onRowClick={(row) => router.push(`/dashboard/tickets/${row.id}`)}
          emptyState={(
            <EmptyState
              icon={<LifeBuoy className="h-6 w-6 text-primary" />}
              title="Ticket yok"
              description="Yeni bir destek talebi oluşturabilirsiniz."
              action={(
                <Button type="button" onClick={() => setIsCreateOpen(true)}>Ticket Oluştur</Button>
              )}
            />
          )}
        />
      </div>

      <Dialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          setIsCreateOpen(open)
          if (!open) setFormErrors({})
        }}
      >
        <DialogContent className="max-w-xl border border-border/70 bg-card/95 shadow-2xl backdrop-blur-xl">
          <DialogHeader>
            <div className="mb-2 flex items-center gap-3">
              <Icon3DBadge icon={MessageSquareWarning} from="from-cyan-500" to="to-blue-500" />
              <div>
                <DialogTitle>Yeni Ticket</DialogTitle>
                <DialogDescription>Destek ekibimize konu ve detayları iletin.</DialogDescription>
              </div>
            </div>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Konu <span className="text-destructive">*</span></Label>
              <Input
                className={cn(
                  'h-11 border-border/70 bg-muted/20',
                  formErrors.subject && 'border-destructive focus-visible:ring-destructive'
                )}
                value={form.subject}
                onChange={(e) => {
                  setForm({ ...form, subject: e.target.value })
                  if (formErrors.subject) setFormErrors((prev) => ({ ...prev, subject: undefined }))
                }}
              />
              {formErrors.subject && <p className="text-xs text-destructive">{formErrors.subject}</p>}
            </div>
            <div className="space-y-2">
              <Label>Öncelik</Label>
              <Select value={form.priority} onValueChange={(value) => setForm({ ...form, priority: value })}>
                <SelectTrigger className="h-11 border-border/70 bg-muted/20">
                  <SelectValue placeholder="Öncelik seç" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Düşük</SelectItem>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="high">Yüksek</SelectItem>
                  <SelectItem value="urgent">Acil</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Mesaj <span className="text-destructive">*</span></Label>
              <Textarea
                rows={6}
                className={cn(
                  'min-h-[120px] border-border/70 bg-muted/20',
                  formErrors.message && 'border-destructive focus-visible:ring-destructive'
                )}
                value={form.message}
                onChange={(e) => {
                  setForm({ ...form, message: e.target.value })
                  if (formErrors.message) setFormErrors((prev) => ({ ...prev, message: undefined }))
                }}
              />
              {formErrors.message && <p className="text-xs text-destructive">{formErrors.message}</p>}
            </div>
          </div>
          <DialogFooter className="mt-6 border-t border-border/70 pt-4">
            <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>İptal</Button>
            <Button
              type="button"
              onClick={handleCreate}
              disabled={createMutation.isPending || !form.subject.trim() || !form.message.trim()}
            >
              Gönder
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
