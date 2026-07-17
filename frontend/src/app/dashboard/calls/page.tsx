'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, Bot, CalendarCheck, PhoneCall, RefreshCw, Settings2, Sparkles } from 'lucide-react'
import { callsApi, voiceAutomationApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'

type CallRow = {
  id: string
  provider: string
  provider_call_id: string
  direction: string
  status: string
  from_number: string
  to_number: string
  duration_seconds: number
  created_at: string
}

type VoiceSettings = {
  enabled: boolean
  provider: string
  from_number?: string | null
  allow_appointment_booking: boolean
  require_explicit_call_request: boolean
  allowed_triggers_json: string[]
  max_attempts_per_lead: number
  cooldown_minutes: number
  daily_call_limit: number
}

type CallIntent = {
  id: string
  customer_phone: string
  customer_name?: string | null
  trigger: string
  reason: string
  status: string
  confidence: number
  created_at: string
}

type VoiceCapabilities = {
  mode: 'dry_run' | 'live'
  live_ready: boolean
  provider: string
  supported_providers: string[]
}

const triggerLabels: Record<string, string> = {
  explicit_call_request: 'Müşteri arama istedi',
  appointment_intent: 'Randevu niyeti',
  price_intent: 'Fiyat niyeti',
  manual_test: 'Test araması',
}

const defaultForm: VoiceSettings = {
  enabled: false,
  provider: 'vapi',
  from_number: '',
  allow_appointment_booking: true,
  require_explicit_call_request: true,
  allowed_triggers_json: ['explicit_call_request', 'appointment_intent'],
  max_attempts_per_lead: 2,
  cooldown_minutes: 240,
  daily_call_limit: 30,
}

export default function CallsPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [form, setForm] = useState<VoiceSettings>(defaultForm)
  const [testPhone, setTestPhone] = useState('')
  const [testName, setTestName] = useState('')

  const settingsQuery = useQuery<VoiceSettings>({
    queryKey: ['voice-settings'],
    queryFn: () => voiceAutomationApi.getSettings().then((res) => res.data),
  })
  const capabilitiesQuery = useQuery<VoiceCapabilities>({
    queryKey: ['voice-capabilities'],
    queryFn: () => voiceAutomationApi.getCapabilities().then((res) => res.data),
  })
  const callsQuery = useQuery<CallRow[]>({
    queryKey: ['calls', 'voice-dashboard'],
    queryFn: () => callsApi.list({ limit: 50 }).then((res) => res.data),
  })
  const intentsQuery = useQuery<CallIntent[]>({
    queryKey: ['voice-intents'],
    queryFn: () => voiceAutomationApi.listIntents({ limit: 20 }).then((res) => res.data),
  })
  const jobsQuery = useQuery({
    queryKey: ['voice-jobs'],
    queryFn: () => voiceAutomationApi.listJobs({ limit: 20 }).then((res) => res.data),
  })

  useEffect(() => {
    if (settingsQuery.data) {
      setForm({
        ...defaultForm,
        ...settingsQuery.data,
        provider: capabilitiesQuery.data?.provider || settingsQuery.data.provider || 'twilio',
        from_number: settingsQuery.data.from_number || '',
        allowed_triggers_json: settingsQuery.data.allowed_triggers_json?.length
          ? settingsQuery.data.allowed_triggers_json
          : defaultForm.allowed_triggers_json,
      })
    }
  }, [capabilitiesQuery.data?.provider, settingsQuery.data])

  const saveMutation = useMutation({
    mutationFn: () => voiceAutomationApi.updateSettings(form).then((res) => res.data),
    onSuccess: (data) => {
      setForm({ ...form, ...data, from_number: data.from_number || '' })
      queryClient.invalidateQueries({ queryKey: ['voice-settings'] })
      toast({ title: 'Arama asistanı güncellendi' })
    },
    onError: (error: any) => {
      toast({
        title: 'Ayarlar kaydedilemedi',
        description: error.response?.data?.detail || 'Lütfen tekrar deneyin.',
        variant: 'destructive',
      })
    },
  })

  const testMutation = useMutation({
    mutationFn: () => voiceAutomationApi.testCall({
      customer_phone: testPhone,
      customer_name: testName || undefined,
      reason: 'Panelden oluşturulan test araması',
    }).then((res) => res.data),
    onSuccess: () => {
      setTestPhone('')
      setTestName('')
      queryClient.invalidateQueries({ queryKey: ['voice-intents'] })
      queryClient.invalidateQueries({ queryKey: ['voice-jobs'] })
      toast({ title: 'Test araması kuyruğa alındı' })
    },
    onError: (error: any) => {
      toast({
        title: 'Test araması oluşturulamadı',
        description: error.response?.data?.detail || 'Telefon numarasını ve arama ayarlarını kontrol edin.',
        variant: 'destructive',
      })
    },
  })

  const columns: DataColumn<CallRow>[] = useMemo(
    () => [
      {
        key: 'to_number',
        header: 'Numara',
        render: (row) => (
          <div className="space-y-1">
            <div className="text-sm font-medium">{row.direction === 'outbound' ? row.to_number : row.from_number}</div>
            <div className="text-xs text-muted-foreground">{row.provider}</div>
          </div>
        ),
      },
      {
        key: 'status',
        header: 'Durum',
        render: (row) => (
          <Badge variant={row.status === 'completed' ? 'success' : row.status === 'failed' ? 'destructive' : 'secondary'}>
            {row.status}
          </Badge>
        ),
      },
      {
        key: 'direction',
        header: 'Yön',
        render: (row) => <Badge variant="outline">{row.direction === 'outbound' ? 'Giden' : 'Gelen'}</Badge>,
      },
      {
        key: 'duration_seconds',
        header: 'Süre',
        render: (row) => <span className="text-sm text-muted-foreground">{Math.round((row.duration_seconds || 0) / 60)} dk</span>,
      },
      {
        key: 'created_at',
        header: 'Tarih',
        render: (row) => <span className="text-sm text-muted-foreground">{new Date(row.created_at).toLocaleString('tr-TR')}</span>,
      },
    ],
    []
  )

  const latestJobStatus = jobsQuery.data?.[0]?.status || 'beklemede yok'
  const isVoiceLive = capabilitiesQuery.data?.live_ready === true

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="AI Arama Asistanı"
          description={isVoiceLive
            ? 'WhatsApp konuşmalarından doğan sıcak müşterileri otomatik arayın, görüşmeleri özetleyin ve randevuları sisteme işleyin.'
            : 'Arama kayıtlarını görüntüleyin. Canlı AI arama özelliği sağlayıcı bağlantısı tamamlandıktan sonra açılacak.'}
          icon={<Icon3DBadge icon={PhoneCall} from="from-emerald-500" to="to-cyan-500" />}
        />

        {!isVoiceLive && (
          <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-medium">Canlı AI arama yakında</p>
              <p className="text-sm opacity-80">Bu ortamda gerçek telefon araması yapılmaz. Mevcut kayıtlar ve güvenli test akışları korunur.</p>
            </div>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-xl border bg-card p-4">
            <div className="flex items-center gap-3">
              <Bot className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Durum</p>
                <p className="font-semibold">{isVoiceLive ? (form.enabled ? 'Aktif' : 'Kapalı') : 'Yakında'}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border bg-card p-4">
            <div className="flex items-center gap-3">
              <Settings2 className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Provider</p>
                <p className="font-semibold uppercase">{form.provider || 'vapi'}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border bg-card p-4">
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Son iş</p>
                <p className="font-semibold">{latestJobStatus}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border bg-card p-4">
            <div className="flex items-center gap-3">
              <CalendarCheck className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Randevu</p>
                <p className="font-semibold">{form.allow_appointment_booking ? 'Açık' : 'Kapalı'}</p>
              </div>
            </div>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Otonom arama ayarları</CardTitle>
            <CardDescription>
              Sistem sadece güvenli koşullarda arama başlatır. Dış provider bağlantısı tamamlanana kadar işler dry-run kayıt olarak oluşur.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-5 lg:grid-cols-3">
            <div className="space-y-2">
              <Label>AI arama asistanı</Label>
              <div className="flex h-11 items-center justify-between rounded-xl border px-3">
                <span className="text-sm">{form.enabled ? 'Aktif' : 'Kapalı'}</span>
                <Switch checked={form.enabled && isVoiceLive} disabled={!isVoiceLive} onCheckedChange={(enabled) => setForm({ ...form, enabled })} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Servis</Label>
              <Select value={form.provider} disabled={!isVoiceLive} onValueChange={(provider) => setForm({ ...form, provider })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="twilio">Twilio</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Arayan numara</Label>
              <Input disabled={!isVoiceLive} value={form.from_number || ''} onChange={(event) => setForm({ ...form, from_number: event.target.value })} placeholder="+905..." />
            </div>
            <div className="space-y-2">
              <Label>Arama koşulu</Label>
              <div className="flex h-11 items-center justify-between rounded-xl border px-3">
                <span className="text-sm">Sadece açık arama isteği</span>
                <Switch
                  checked={form.require_explicit_call_request}
                  onCheckedChange={(require_explicit_call_request) => setForm({ ...form, require_explicit_call_request })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Randevu oluşturma</Label>
              <div className="flex h-11 items-center justify-between rounded-xl border px-3">
                <span className="text-sm">Görüşmeden randevu aç</span>
                <Switch
                  checked={form.allow_appointment_booking}
                  onCheckedChange={(allow_appointment_booking) => setForm({ ...form, allow_appointment_booking })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Günlük limit</Label>
              <Input
                type="number"
                min={0}
                value={form.daily_call_limit}
                onChange={(event) => setForm({ ...form, daily_call_limit: Number(event.target.value) })}
              />
            </div>
            <div className="space-y-2">
              <Label>Maksimum deneme</Label>
              <Input
                type="number"
                min={1}
                value={form.max_attempts_per_lead}
                onChange={(event) => setForm({ ...form, max_attempts_per_lead: Number(event.target.value) })}
              />
            </div>
            <div className="space-y-2">
              <Label>Tekrar arama bekleme</Label>
              <Input
                type="number"
                min={1}
                value={form.cooldown_minutes}
                onChange={(event) => setForm({ ...form, cooldown_minutes: Number(event.target.value) })}
              />
            </div>
            <div className="flex items-end">
              <Button className="w-full" onClick={() => saveMutation.mutate()} disabled={!isVoiceLive || saveMutation.isPending || settingsQuery.isLoading}>
                {saveMutation.isPending && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
                Ayarları Kaydet
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Test araması</CardTitle>
            <CardDescription>Numara ve kurallar doğruysa sistem aynı otomatik kuyruğu kullanarak bir test işi üretir.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
            <div className="space-y-2">
              <Label>Telefon</Label>
              <Input value={testPhone} onChange={(event) => setTestPhone(event.target.value)} placeholder="+905..." />
            </div>
            <div className="space-y-2">
              <Label>İsim</Label>
              <Input value={testName} onChange={(event) => setTestName(event.target.value)} placeholder="Müşteri adı" />
            </div>
            <div className="flex items-end">
              <Button variant="outline" onClick={() => testMutation.mutate()} disabled={!isVoiceLive || !testPhone || testMutation.isPending}>
                {isVoiceLive ? 'Test Oluştur' : 'Yakında'}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">Otomatik arama niyetleri</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(intentsQuery.data || []).length === 0 ? (
                <EmptyState
                  icon={<Sparkles className="h-6 w-6 text-primary" />}
                  title="Henüz otomatik arama niyeti yok"
                  description="Müşteri WhatsApp üzerinden arama istediğinde burada görünecek."
                />
              ) : (
                (intentsQuery.data || []).map((intent) => (
                  <div key={intent.id} className="rounded-xl border p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{intent.customer_name || intent.customer_phone}</p>
                        <p className="text-sm text-muted-foreground">{triggerLabels[intent.trigger] || intent.trigger}</p>
                      </div>
                      <Badge variant={intent.status === 'queued' ? 'success' : 'secondary'}>{intent.status}</Badge>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">{intent.reason}</p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-xl">Arama kayıtları</CardTitle>
            </CardHeader>
            <CardContent>
              <DataTable
                columns={columns}
                data={callsQuery.data || []}
                loading={callsQuery.isLoading}
                onRowClick={(row) => router.push(`/dashboard/calls/${row.id}`)}
                emptyState={(
                  <EmptyState
                    icon={<PhoneCall className="h-6 w-6 text-primary" />}
                    title="Henüz çağrı yok"
                    description="AI arama asistanı çağrı oluşturduğunda burada listelenecek."
                  />
                )}
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </ContentContainer>
  )
}
