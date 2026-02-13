'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Filter, Plus } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { FilterBar } from '@/components/shared/filter-bar'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { systemEventsApi, ticketsApi } from '@/lib/api'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { useToast } from '@/components/ui/use-toast'

export default function ErrorsPage() {
  const { toast } = useToast()
  const [level, setLevel] = useState<string | undefined>()
  const [source, setSource] = useState<string | undefined>()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [ticketForm, setTicketForm] = useState({ subject: '', priority: 'normal', message: '' })

  const { data: events, isLoading } = useQuery({
    queryKey: ['system-events', level, source],
    queryFn: () => systemEventsApi.list({ skip: 0, limit: 50, level, source }).then(res => res.data),
  })

  const columns: DataColumn<any>[] = [
    {
      key: 'code',
      header: 'Kod',
      render: (row) => <span className="font-medium">{row.code}</span>,
    },
    {
      key: 'message',
      header: 'Mesaj',
      render: (row) => <span className="text-sm text-muted-foreground">{row.message}</span>,
    },
    {
      key: 'source',
      header: 'Kaynak',
      render: (row) => <Badge variant="outline">{row.source}</Badge>,
    },
    {
      key: 'level',
      header: 'Seviye',
      render: (row) => <Badge variant={row.level === 'error' ? 'destructive' : 'secondary'}>{row.level}</Badge>,
    },
    {
      key: 'action',
      header: '',
      render: (row) => (
        <Button
          size="sm"
          variant="outline"
          onClick={(event) => {
            event.stopPropagation()
            setTicketForm({
              subject: `Error: ${row.code}`,
              priority: row.level === 'error' ? 'high' : 'normal',
              message: `${row.message}\n\nKaynak: ${row.source}\nSeviye: ${row.level}`,
            })
            setIsCreateOpen(true)
          }}
        >
          <Plus className="h-4 w-4 mr-2" />
          Ticket Aç
        </Button>
      ),
    },
  ]

  const handleCreateTicket = async () => {
    try {
      await ticketsApi.create(ticketForm)
      toast({ title: 'Ticket oluşturuldu' })
      setIsCreateOpen(false)
      setTicketForm({ subject: '', priority: 'normal', message: '' })
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Ticket oluşturulamadı',
        variant: 'destructive',
      })
    }
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Hata Merkezi"
          description="Sistemdeki hata ve uyarıları takip edin."
          actions={(
            <Button variant="outline" size="sm" onClick={() => { setLevel(undefined); setSource(undefined) }}>
              <Filter className="h-4 w-4 mr-2" />
              Filtreleri Temizle
            </Button>
          )}
        />

        <FilterBar
          searchPlaceholder="Hata kodu ara..."
          onSearchChange={() => {}}
        />

        <DataTable
          columns={columns}
          data={events || []}
          loading={isLoading}
          emptyState={(
            <EmptyState
              icon={<AlertTriangle className="h-6 w-6 text-primary" />}
              title="Hata bulunamadı"
              description="Bu tenant için kayıtlı hata yok."
            />
          )}
        />
      </div>

      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Ticket Oluştur</DialogTitle>
            <DialogDescription>Hata kaydını destek ekibine iletin.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Konu</Label>
              <Input value={ticketForm.subject} onChange={(e) => setTicketForm({ ...ticketForm, subject: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Öncelik</Label>
              <Input value={ticketForm.priority} onChange={(e) => setTicketForm({ ...ticketForm, priority: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Mesaj</Label>
              <Textarea rows={6} value={ticketForm.message} onChange={(e) => setTicketForm({ ...ticketForm, message: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>İptal</Button>
            <Button onClick={handleCreateTicket}>Gönder</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
