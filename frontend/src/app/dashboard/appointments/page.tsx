'use client'

import { useEffect, useMemo, useState } from 'react'
import { CalendarCheck, Loader2, Plus } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { appointmentsApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

interface Appointment {
  id: string
  customer_name: string
  customer_email: string | null
  subject: string
  starts_at: string
  notes: string | null
  status: 'scheduled' | 'completed' | 'cancelled'
}

export default function AppointmentsPage() {
  const { toast } = useToast()
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    customer_name: '',
    customer_email: '',
    subject: '',
    starts_at: '',
    notes: '',
    reminder_before_minutes: '60',
  })

  const fetchAppointments = async () => {
    setLoading(true)
    try {
      const response = await appointmentsApi.list()
      setAppointments(response.data || [])
    } catch (error: any) {
      toast({
        title: 'Randevular alınamadı',
        description: error.response?.data?.detail || 'Lütfen tekrar deneyin.',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAppointments()
    appointmentsApi.sendReminders().catch(() => undefined)
  }, [])

  const columns: DataColumn<Appointment>[] = useMemo(() => [
    { key: 'customer_name', header: 'Müşteri', render: (row) => <span className="font-medium">{row.customer_name}</span> },
    { key: 'subject', header: 'Konu', render: (row) => <span className="text-sm">{row.subject}</span> },
    { key: 'starts_at', header: 'Tarih', render: (row) => <span className="text-sm text-muted-foreground">{new Date(row.starts_at).toLocaleString('tr-TR')}</span> },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <Badge variant={row.status === 'scheduled' ? 'outline' : row.status === 'completed' ? 'secondary' : 'destructive'}>
          {row.status}
        </Badge>
      ),
    },
  ], [])

  const handleCreate = async () => {
    setSubmitting(true)
    try {
      await appointmentsApi.create({
        customer_name: form.customer_name || 'Yeni Müşteri',
        customer_email: form.customer_email || undefined,
        subject: form.subject || 'Genel',
        starts_at: new Date(form.starts_at).toISOString(),
        notes: form.notes || undefined,
        reminder_before_minutes: Number(form.reminder_before_minutes) || 60,
      })
      toast({
        title: 'Randevu oluşturuldu',
        description: 'Müşteri e-postası varsa otomatik bilgilendirme gönderildi.',
      })
      await fetchAppointments()
      setForm({
        customer_name: '',
        customer_email: '',
        subject: '',
        starts_at: '',
        notes: '',
        reminder_before_minutes: '60',
      })
      setOpen(false)
    } catch (error: any) {
      toast({
        title: 'Randevu oluşturulamadı',
        description: error.response?.data?.detail || 'Lütfen alanları kontrol edin.',
        variant: 'destructive',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Randevular"
          description="Randevu planlayıcı tool’u ile oluşturulan kayıtları yönetin."
          icon={<Icon3DBadge icon={CalendarCheck} from="from-emerald-500" to="to-teal-500" />}
          actions={(
            <Button onClick={() => setOpen(true)} className="bg-gradient-to-r from-blue-600 to-violet-600 btn-shimmer shadow-lg shadow-blue-500/25">
              <Plus className="mr-2 h-4 w-4" />
              Randevu Oluştur
            </Button>
          )}
        />

        <DataTable
          columns={columns}
          data={appointments}
          loading={loading}
          emptyState={(
            <EmptyState
              icon={<CalendarCheck className="h-6 w-6 text-primary" />}
              title="Randevu yok"
              description="Henüz planlanmış randevu bulunmuyor."
            />
          )}
        />
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="glass-card">
          <DialogHeader>
            <DialogTitle>Yeni Randevu</DialogTitle>
            <DialogDescription>Müşteri randevusunu hızlıca oluşturun.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="appointment-customer">Müşteri</Label>
              <Input
                id="appointment-customer"
                value={form.customer_name}
                onChange={(event) => setForm((prev) => ({ ...prev, customer_name: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="appointment-email">Müşteri E-posta</Label>
              <Input
                id="appointment-email"
                type="email"
                value={form.customer_email}
                onChange={(event) => setForm((prev) => ({ ...prev, customer_email: event.target.value }))}
                placeholder="musteri@email.com"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="appointment-service">Konu</Label>
              <Input
                id="appointment-service"
                value={form.subject}
                onChange={(event) => setForm((prev) => ({ ...prev, subject: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="appointment-date">Tarih</Label>
              <Input
                id="appointment-date"
                type="datetime-local"
                value={form.starts_at}
                onChange={(event) => setForm((prev) => ({ ...prev, starts_at: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="appointment-reminder">Hatırlatma (dakika önce)</Label>
              <Input
                id="appointment-reminder"
                type="number"
                min={5}
                value={form.reminder_before_minutes}
                onChange={(event) => setForm((prev) => ({ ...prev, reminder_before_minutes: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="appointment-notes">Notlar</Label>
              <Textarea
                id="appointment-notes"
                value={form.notes}
                onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
                placeholder="Randevu detayları..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Vazgeç</Button>
            <Button onClick={handleCreate} className="bg-gradient-to-r from-blue-600 to-violet-600" disabled={submitting || !form.starts_at}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
