'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CalendarCheck,
  CalendarClock,
  Clock3,
  ExternalLink,
  Loader2,
  Plus,
  Save,
  Settings2,
  Trash2,
} from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  AppointmentAvailability,
  AppointmentSettings,
  appointmentsApi,
} from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

interface Appointment {
  id: string
  customer_name: string
  customer_email: string | null
  customer_phone: string | null
  subject: string
  starts_at: string
  duration_minutes: number
  source: string
  notes: string | null
  status: 'scheduled' | 'completed' | 'cancelled'
}

const DAY_LABELS: Record<string, string> = {
  monday: 'Pazartesi',
  tuesday: 'Salı',
  wednesday: 'Çarşamba',
  thursday: 'Perşembe',
  friday: 'Cuma',
  saturday: 'Cumartesi',
  sunday: 'Pazar',
}

export default function AppointmentsPage() {
  const { toast } = useToast()
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [settings, setSettings] = useState<AppointmentSettings | null>(null)
  const [availability, setAvailability] = useState<AppointmentAvailability | null>(null)
  const [activeTab, setActiveTab] = useState('appointments')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [savingSettings, setSavingSettings] = useState(false)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    service_id: '',
    starts_at: '',
    notes: '',
    reminder_before_minutes: '60',
  })

  const fetchPage = useCallback(async () => {
    setLoading(true)
    try {
      const [appointmentsResponse, settingsResponse, availabilityResponse] = await Promise.all([
        appointmentsApi.list(),
        appointmentsApi.getSettings(),
        appointmentsApi.getAvailability({ days: 14 }),
      ])
      setAppointments(appointmentsResponse.data || [])
      setSettings(settingsResponse.data)
      setAvailability(availabilityResponse.data)
      if (!settingsResponse.data?.configured) setActiveTab('schedule')
      const firstService = settingsResponse.data?.services?.find((item: { active: boolean }) => item.active)
      if (firstService) {
        setForm((current) => ({ ...current, service_id: current.service_id || firstService.id }))
      }
    } catch (error: any) {
      toast({
        title: 'Randevu alanı açılamadı',
        description: error.response?.data?.detail || 'Lütfen tekrar deneyin.',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    fetchPage()
  }, [fetchPage])

  const columns: DataColumn<Appointment>[] = useMemo(() => [
    {
      key: 'customer_name',
      header: 'Müşteri',
      render: (row) => (
        <div>
          <p className="font-medium">{row.customer_name}</p>
          <p className="text-xs text-muted-foreground">{row.customer_phone || row.customer_email || 'İletişim bilgisi yok'}</p>
        </div>
      ),
    },
    {
      key: 'subject',
      header: 'Hizmet',
      render: (row) => (
        <div>
          <p className="text-sm">{row.subject}</p>
          <p className="text-xs text-muted-foreground">{row.duration_minutes} dakika</p>
        </div>
      ),
    },
    { key: 'starts_at', header: 'Tarih', render: (row) => <span className="text-sm text-muted-foreground">{new Date(row.starts_at).toLocaleString('tr-TR')}</span> },
    {
      key: 'source',
      header: 'Kaynak',
      render: (row) => <Badge variant="outline">{row.source === 'ai_conversation' ? 'SvontAI' : 'Manuel'}</Badge>,
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <Badge variant={row.status === 'scheduled' ? 'outline' : row.status === 'completed' ? 'secondary' : 'destructive'}>
          {row.status === 'scheduled' ? 'Planlandı' : row.status === 'completed' ? 'Tamamlandı' : 'İptal'}
        </Badge>
      ),
    },
  ], [])

  const selectedService = settings?.services.find((item) => item.id === form.service_id)
  const serviceSlots = (availability?.slots || []).filter((slot) => slot.service_id === form.service_id)

  const handleCreate = async () => {
    if (!selectedService || !form.starts_at) return
    setSubmitting(true)
    try {
      await appointmentsApi.create({
        customer_name: form.customer_name || 'Yeni müşteri',
        customer_email: form.customer_email || undefined,
        customer_phone: form.customer_phone || undefined,
        subject: selectedService.name,
        starts_at: new Date(form.starts_at).toISOString(),
        duration_minutes: selectedService.duration_minutes,
        notes: form.notes || undefined,
        reminder_before_minutes: Number(form.reminder_before_minutes) || 60,
      })
      toast({ title: 'Randevu oluşturuldu' })
      setForm({
        customer_name: '',
        customer_email: '',
        customer_phone: '',
        service_id: settings?.services.find((item) => item.active)?.id || '',
        starts_at: '',
        notes: '',
        reminder_before_minutes: '60',
      })
      setOpen(false)
      await fetchPage()
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

  const updateService = (index: number, field: 'name' | 'duration_minutes' | 'active', value: string | number | boolean) => {
    setSettings((current) => {
      if (!current) return current
      const services = current.services.map((service, serviceIndex) => (
        serviceIndex === index ? { ...service, [field]: value } : service
      ))
      return { ...current, services }
    })
  }

  const addService = () => {
    setSettings((current) => current ? {
      ...current,
      services: [
        ...current.services,
        { id: `service-${Date.now()}`, name: 'Yeni hizmet', duration_minutes: 60, active: true },
      ],
    } : current)
  }

  const removeService = (index: number) => {
    setSettings((current) => current ? {
      ...current,
      services: current.services.filter((_, serviceIndex) => serviceIndex !== index),
    } : current)
  }

  const saveSettings = async () => {
    if (!settings) return
    setSavingSettings(true)
    try {
      const response = await appointmentsApi.updateSettings(settings)
      setSettings(response.data)
      const availabilityResponse = await appointmentsApi.getAvailability({ days: 14 })
      setAvailability(availabilityResponse.data)
      toast({ title: 'Çalışma planı kaydedildi' })
    } catch (error: any) {
      toast({
        title: 'Ayarlar kaydedilemedi',
        description: error.response?.data?.detail || 'Saatleri ve hizmetleri kontrol edin.',
        variant: 'destructive',
      })
    } finally {
      setSavingSettings(false)
    }
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Randevular"
          description="Müşteri randevuları ve işletme çalışma planı"
          icon={<Icon3DBadge icon={CalendarCheck} from="from-emerald-500" to="to-teal-500" />}
          actions={(
            <Button onClick={() => setOpen(true)} disabled={!settings?.configured || !availability?.slots.length || loading}>
              <Plus className="mr-2 h-4 w-4" />
              Randevu Oluştur
            </Button>
          )}
        />

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full max-w-md grid-cols-2">
            <TabsTrigger value="appointments"><CalendarCheck className="mr-2 h-4 w-4" />Randevular</TabsTrigger>
            <TabsTrigger value="schedule"><Settings2 className="mr-2 h-4 w-4" />Çalışma Planı</TabsTrigger>
          </TabsList>

          <TabsContent value="appointments">
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
          </TabsContent>

          <TabsContent value="schedule" className="space-y-8">
            {loading || !settings ? (
              <div className="flex min-h-48 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
            ) : (
              <>
                <section className="space-y-4 border-b border-border/70 pb-8">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h2 className="text-base font-semibold">Hizmetler</h2>
                      <p className="text-sm text-muted-foreground">Randevu türü ve süresi</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={addService}><Plus className="mr-2 h-4 w-4" />Hizmet</Button>
                  </div>
                  <div className="space-y-3">
                    {settings.services.map((service, index) => (
                      <div key={service.id} className="grid gap-3 rounded-lg border border-border/70 p-4 sm:grid-cols-[minmax(0,1fr)_140px_auto_auto] sm:items-end">
                        <div className="grid gap-2">
                          <Label htmlFor={`service-name-${service.id}`}>Hizmet adı</Label>
                          <Input id={`service-name-${service.id}`} value={service.name} onChange={(event) => updateService(index, 'name', event.target.value)} />
                        </div>
                        <div className="grid gap-2">
                          <Label htmlFor={`service-duration-${service.id}`}>Süre</Label>
                          <Select value={String(service.duration_minutes)} onValueChange={(value) => updateService(index, 'duration_minutes', Number(value))}>
                            <SelectTrigger id={`service-duration-${service.id}`}><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {[15, 30, 45, 60, 90, 120].map((minutes) => <SelectItem key={minutes} value={String(minutes)}>{minutes} dk</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="flex h-10 items-center gap-2">
                          <Switch checked={service.active} onCheckedChange={(checked) => updateService(index, 'active', checked)} aria-label={`${service.name} aktif`} />
                          <span className="text-sm">Aktif</span>
                        </div>
                        <Button variant="ghost" size="icon" onClick={() => removeService(index)} disabled={settings.services.length === 1} title="Hizmeti sil">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="space-y-4 border-b border-border/70 pb-8">
                  <div>
                    <h2 className="text-base font-semibold">Çalışma saatleri</h2>
                    <p className="text-sm text-muted-foreground">Haftalık müsaitlik</p>
                  </div>
                  <div className="divide-y divide-border/70 rounded-lg border border-border/70">
                    {Object.entries(settings.weekly_hours).map(([day, hours]) => (
                      <div key={day} className="grid gap-3 p-4 sm:grid-cols-[150px_1fr_1fr] sm:items-center">
                        <div className="flex items-center gap-3">
                          <Switch
                            checked={hours.enabled}
                            onCheckedChange={(checked) => setSettings((current) => current ? {
                              ...current,
                              weekly_hours: { ...current.weekly_hours, [day]: { ...hours, enabled: checked } },
                            } : current)}
                            aria-label={`${DAY_LABELS[day]} çalışma durumu`}
                          />
                          <span className="text-sm font-medium">{DAY_LABELS[day]}</span>
                        </div>
                        <Input
                          type="time"
                          value={hours.start}
                          disabled={!hours.enabled}
                          onChange={(event) => setSettings((current) => current ? {
                            ...current,
                            weekly_hours: { ...current.weekly_hours, [day]: { ...hours, start: event.target.value } },
                          } : current)}
                          aria-label={`${DAY_LABELS[day]} başlangıç`}
                        />
                        <Input
                          type="time"
                          value={hours.end}
                          disabled={!hours.enabled}
                          onChange={(event) => setSettings((current) => current ? {
                            ...current,
                            weekly_hours: { ...current.weekly_hours, [day]: { ...hours, end: event.target.value } },
                          } : current)}
                          aria-label={`${DAY_LABELS[day]} bitiş`}
                        />
                      </div>
                    ))}
                  </div>
                </section>

                <section className="space-y-4 border-b border-border/70 pb-8">
                  <div>
                    <h2 className="text-base font-semibold">Rezervasyon kuralları</h2>
                    <p className="text-sm text-muted-foreground">Saat dilimi, bildirim ve konum</p>
                  </div>
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="grid gap-2">
                      <Label>Saat dilimi</Label>
                      <Select value={settings.timezone} onValueChange={(timezone) => setSettings({ ...settings, timezone })}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Europe/Istanbul">Türkiye</SelectItem>
                          <SelectItem value="Europe/Berlin">Orta Avrupa</SelectItem>
                          <SelectItem value="Europe/London">Birleşik Krallık</SelectItem>
                          <SelectItem value="UTC">UTC</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="minimum-notice">En erken randevu</Label>
                      <Select value={String(settings.minimum_notice_hours)} onValueChange={(value) => setSettings({ ...settings, minimum_notice_hours: Number(value) })}>
                        <SelectTrigger id="minimum-notice"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {[0, 1, 2, 4, 12, 24, 48].map((hours) => <SelectItem key={hours} value={String(hours)}>{hours === 0 ? 'Hemen' : `${hours} saat sonra`}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="booking-window">İleri tarih sınırı</Label>
                      <Select value={String(settings.booking_window_days)} onValueChange={(value) => setSettings({ ...settings, booking_window_days: Number(value) })}>
                        <SelectTrigger id="booking-window"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {[7, 14, 30, 60, 90].map((days) => <SelectItem key={days} value={String(days)}>{days} gün</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="grid gap-2">
                      <Label htmlFor="booking-location">Görüşme konumu veya bağlantısı</Label>
                      <Input id="booking-location" value={settings.booking_location} onChange={(event) => setSettings({ ...settings, booking_location: event.target.value })} placeholder="Adres veya toplantı bağlantısı" />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="booking-notes">İşletme randevu notu</Label>
                      <Input id="booking-notes" value={settings.booking_notes} onChange={(event) => setSettings({ ...settings, booking_notes: event.target.value })} placeholder="Randevu öncesi gerekli bilgi" />
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Button asChild variant="outline"><Link href="/dashboard/integrations"><ExternalLink className="mr-2 h-4 w-4" />Google Calendar</Link></Button>
                    <Button onClick={saveSettings} disabled={savingSettings || settings.services.some((service) => !service.name.trim())}>
                      {savingSettings ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                      Kaydet
                    </Button>
                  </div>
                </section>

                <section className="space-y-4">
                  <div className="flex items-center gap-3">
                    <Clock3 className="h-5 w-5 text-primary" />
                    <div>
                      <h2 className="text-base font-semibold">Yaklaşan boşluklar</h2>
                      <p className="text-sm text-muted-foreground">{availability?.calendar_connected ? 'Google Calendar dahil' : 'SvontAI çalışma planı'}</p>
                    </div>
                  </div>
                  {availability?.warnings.map((warning) => <p key={warning} className="text-sm text-amber-700">{warning}</p>)}
                  <div className="flex flex-wrap gap-2">
                    {(availability?.slots || []).slice(0, 12).map((slot) => (
                      <Badge key={`${slot.service_id}-${slot.start_at}`} variant="outline" className="px-3 py-2 font-normal">
                        {slot.local_label} · {slot.service_name}
                      </Badge>
                    ))}
                    {!availability?.slots.length && <p className="text-sm text-muted-foreground">Uygun boşluk bulunmuyor.</p>}
                  </div>
                </section>
              </>
            )}
          </TabsContent>
        </Tabs>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Yeni randevu</DialogTitle>
            <DialogDescription>Müşteri ve hizmet bilgileri</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2 sm:col-span-2">
              <Label htmlFor="appointment-customer">Müşteri</Label>
              <Input id="appointment-customer" value={form.customer_name} onChange={(event) => setForm((prev) => ({ ...prev, customer_name: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="appointment-phone">Telefon</Label>
              <Input id="appointment-phone" type="tel" value={form.customer_phone} onChange={(event) => setForm((prev) => ({ ...prev, customer_phone: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="appointment-email">E-posta</Label>
              <Input id="appointment-email" type="email" value={form.customer_email} onChange={(event) => setForm((prev) => ({ ...prev, customer_email: event.target.value }))} />
            </div>
            <div className="grid gap-2">
              <Label>Hizmet</Label>
              <Select value={form.service_id} onValueChange={(service_id) => setForm((prev) => ({ ...prev, service_id }))}>
                <SelectTrigger><SelectValue placeholder="Hizmet seçin" /></SelectTrigger>
                <SelectContent>
                  {settings?.services.filter((service) => service.active).map((service) => (
                    <SelectItem key={service.id} value={service.id}>{service.name} · {service.duration_minutes} dk</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Boş saat</Label>
              <Select value={form.starts_at} onValueChange={(starts_at) => setForm((prev) => ({ ...prev, starts_at }))}>
                <SelectTrigger><SelectValue placeholder="Saat seçin" /></SelectTrigger>
                <SelectContent>
                  {serviceSlots.slice(0, 60).map((slot) => (
                    <SelectItem key={slot.start_at} value={slot.start_at}>{slot.local_label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2 sm:col-span-2">
              <Label htmlFor="appointment-notes">Not</Label>
              <Textarea id="appointment-notes" value={form.notes} onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Vazgeç</Button>
            <Button onClick={handleCreate} disabled={submitting || !form.starts_at || !selectedService}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <CalendarClock className="mr-2 h-4 w-4" />
              Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
