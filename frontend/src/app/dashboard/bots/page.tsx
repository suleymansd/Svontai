'use client'

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import {
  AlertCircle,
  BookOpen,
  Bot,
  CalendarDays,
  CheckCircle2,
  Headphones,
  Image as ImageIcon,
  Loader2,
  Save,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ContentContainer } from '@/components/shared/content-container'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { PageHeader } from '@/components/shared/page-header'
import { autopilotApi, botApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { useToast } from '@/components/ui/use-toast'
import { AssistantSimulator } from '@/components/bots/assistant-simulator'
import { ConversationalBotTrainer } from '@/components/bots/conversational-bot-trainer'

type Training = {
  goal: 'support' | 'sales' | 'appointments' | 'mixed'
  tone: 'formal' | 'friendly' | 'professional' | 'casual'
  response_length: 'concise' | 'balanced' | 'detailed'
  price_policy: 'known_only' | 'confirm_before_sending' | 'never_share'
  handoff_mode: 'automatic' | 'suggest' | 'manual'
  business_summary: string
}

type Capability = {
  key: string
  name: string
  description: string
  enabled: boolean
  ready: boolean
  status: 'active' | 'needs_setup' | 'disabled'
  missing_requirements: string[]
  config: Record<string, unknown>
  locked: boolean
}

type AssistantProfile = {
  assistant: {
    id: string
    name: string
    description?: string
    is_active: boolean
    primary_color: string
  }
  training: Training
  capabilities: Capability[]
  completion_percent: number
}

type SpecialistBot = {
  id: string
  name: string
  description?: string | null
  is_active: boolean
  assistant_type: 'primary' | 'specialist'
}

const capabilityIcons: Record<string, typeof BookOpen> = {
  knowledge_support: BookOpen,
  lead_qualification: Users,
  appointment_management: CalendarDays,
  human_handoff: Headphones,
  media_catalog: ImageIcon,
}

const trainingOptions = {
  goal: [
    ['mixed', 'Tümü'], ['support', 'Destek'], ['sales', 'Satış'], ['appointments', 'Randevu'],
  ],
  tone: [
    ['professional', 'Profesyonel'], ['friendly', 'Samimi'], ['formal', 'Resmi'], ['casual', 'Rahat'],
  ],
  response_length: [
    ['concise', 'Kısa'], ['balanced', 'Dengeli'], ['detailed', 'Detaylı'],
  ],
  price_policy: [
    ['known_only', 'Bilinen fiyatı paylaş'],
    ['confirm_before_sending', 'Önce ihtiyacı netleştir'],
    ['never_share', 'Teklife yönlendir'],
  ],
  handoff_mode: [
    ['automatic', 'Gerektiğinde otomatik'], ['suggest', 'Önce müşteriye sor'], ['manual', 'Sadece benim komutumla'],
  ],
} as const

function ChoiceGroup({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: readonly (readonly [string, string])[]
  onChange: (value: string) => void
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex flex-wrap gap-2">
        {options.map(([optionValue, optionLabel]) => (
          <Button
            key={optionValue}
            type="button"
            size="sm"
            variant={value === optionValue ? 'default' : 'outline'}
            onClick={() => onChange(optionValue)}
          >
            {optionLabel}
          </Button>
        ))}
      </div>
    </div>
  )
}

export default function BotsPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [trainingOpen, setTrainingOpen] = useState(false)
  const [training, setTraining] = useState<Training | null>(null)

  const { data: profile, isLoading } = useQuery<AssistantProfile>({
    queryKey: ['assistant-profile'],
    queryFn: () => botApi.getAssistantProfile().then((response) => response.data),
  })

  const { data: bots = [] } = useQuery<SpecialistBot[]>({
    queryKey: ['bots'],
    queryFn: () => botApi.list().then((response) => response.data),
  })
  const specialists = bots.filter((bot) => bot.assistant_type === 'specialist')

  useEffect(() => {
    if (profile) setTraining(profile.training)
  }, [profile])

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['assistant-profile'] })
    queryClient.invalidateQueries({ queryKey: ['bots'] })
  }

  const trainingMutation = useMutation({
    mutationFn: (data: Training) => botApi.updateAssistantTraining(data),
    onSuccess: () => {
      refresh()
      setTrainingOpen(false)
      toast({ title: 'Ana asistan eğitildi', description: 'Seçimleriniz tüm uzman yeteneklere uygulandı.' })
    },
    onError: (error) => toast({
      title: 'Ayarlar kaydedilemedi',
      description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
      variant: 'destructive',
    }),
  })

  const capabilityMutation = useMutation({
    mutationFn: ({ key, enabled, config }: { key: string; enabled: boolean; config: Record<string, unknown> }) =>
      botApi.updateAssistantCapability(key, { enabled, config }),
    onSuccess: () => {
      refresh()
      toast({ title: 'Yetenek güncellendi', description: 'Ana asistan yeni ayarla çalışmaya hazır.' })
    },
    onError: (error) => toast({
      title: 'Yetenek güncellenemedi',
      description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
      variant: 'destructive',
    }),
  })

  const autopilotMutation = useMutation({
    mutationFn: () => autopilotApi.run(),
    onSuccess: () => {
      refresh()
      toast({ title: 'Bilgiler yenilendi', description: 'İşletme profiliniz ana asistana yeniden işlendi.' })
    },
    onError: (error) => toast({
      title: 'Yenileme tamamlanamadı',
      description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
      variant: 'destructive',
    }),
  })

  const toggleCapability = (capability: Capability, enabled: boolean) => {
    capabilityMutation.mutate({ key: capability.key, enabled, config: capability.config || {} })
  }

  if (isLoading || !profile || !training) {
    return (
      <ContentContainer>
        <div className="space-y-6">
          <Skeleton className="h-12 w-72" />
          <Skeleton className="h-64 w-full" />
          <div className="grid gap-4 md:grid-cols-2"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>
        </div>
      </ContentContainer>
    )
  }

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="AI Asistanım"
          description="Tek ana asistanınız, işletme bilginizi ve uzman yetenekleri birlikte kullanır."
          icon={<Icon3DBadge icon={Bot} from="from-primary" to="to-cyan-500" />}
          actions={(
            <div className="flex flex-wrap gap-2">
              <ConversationalBotTrainer onApplied={refresh} />
              <AssistantSimulator botId={profile.assistant.id} />
              <Button variant="outline" onClick={() => autopilotMutation.mutate()} disabled={autopilotMutation.isPending}>
                {autopilotMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                İşletme Bilgilerini Yenile
              </Button>
            </div>
          )}
        />

        <section className="grid gap-6 border-y border-border/70 py-6 lg:grid-cols-[1.4fr_0.6fr]">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <Bot className="h-7 w-7 text-primary" />
              </div>
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl font-semibold">{profile.assistant.name}</h2>
                  <Badge variant="success">Ana Asistan</Badge>
                  <Badge variant={profile.assistant.is_active ? 'success' : 'secondary'}>
                    {profile.assistant.is_active ? 'Çalışıyor' : 'Pasif'}
                  </Badge>
                </div>
                <p className="max-w-2xl text-sm text-muted-foreground">
                  {profile.assistant.description || 'İşletme mesajlarını tek merkezden yöneten ana asistan.'}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button onClick={() => setTrainingOpen(true)}><Settings2 className="mr-2 h-4 w-4" />Davranışı Ayarla</Button>
              <Button asChild variant="outline"><Link href={`/dashboard/bots/${profile.assistant.id}/knowledge`}><BookOpen className="mr-2 h-4 w-4" />Bilgiler</Link></Button>
            </div>
          </div>
          <div className="border-l-0 border-border/70 lg:border-l lg:pl-6">
            <div className="flex items-center justify-between text-sm"><span className="font-medium">Eğitim durumu</span><span>%{profile.completion_percent}</span></div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full bg-primary transition-all" style={{ width: `${profile.completion_percent}%` }} />
            </div>
            <p className="mt-3 text-xs text-muted-foreground">Prompt yazmanız gerekmez; seçimleriniz otomatik çalışma talimatına çevrilir.</p>
          </div>
        </section>

        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Uzman Yetenekler</h2>
            <p className="text-sm text-muted-foreground">Yetenekler ayrı ayrı çalışır, müşteriye yalnızca Ana Asistan yanıt verir.</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {profile.capabilities.map((capability) => {
              const Icon = capabilityIcons[capability.key] || ShieldCheck
              return (
                <Card key={capability.key} className="border-border/70">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted"><Icon className="h-5 w-5" /></div>
                        <div className="min-w-0"><CardTitle className="text-base">{capability.name}</CardTitle><p className="mt-1 text-xs text-muted-foreground">{capability.status === 'active' ? 'Hazır ve aktif' : capability.status === 'needs_setup' ? 'Kurulum gerekiyor' : 'Kapalı'}</p></div>
                      </div>
                      <Switch
                        checked={capability.enabled}
                        disabled={capability.locked || capabilityMutation.isPending}
                        onCheckedChange={(enabled) => toggleCapability(capability, enabled)}
                        aria-label={`${capability.name} durumunu değiştir`}
                      />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="min-h-10 text-sm text-muted-foreground">{capability.description}</p>
                    {capability.status === 'active' ? (
                      <div className="flex items-center gap-2 text-xs text-emerald-700"><CheckCircle2 className="h-4 w-4" />Ana asistana bağlı</div>
                    ) : capability.status === 'needs_setup' ? (
                      <div className="space-y-2"><div className="flex items-start gap-2 text-xs text-amber-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{capability.missing_requirements[0]}</div></div>
                    ) : null}
                    {capability.key === 'media_catalog' && (
                      <Button asChild variant="outline" size="sm"><Link href="/dashboard/media"><ImageIcon className="mr-2 h-4 w-4" />Medya Kütüphanesi</Link></Button>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </section>

        <section className="space-y-4 border-t border-border/70 pt-6">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Özel Uzmanlar</h2>
              <p className="text-sm text-muted-foreground">
                Belirli müşteri sorularına odaklanan uzmanlar, yanıtlarını Ana Asistan üzerinden verir.
              </p>
            </div>
            <Badge variant="secondary">{specialists.length} uzman</Badge>
          </div>
          {specialists.length === 0 ? (
            <div className="border-y border-dashed py-8 text-center">
              <p className="text-sm font-medium">Henüz özel uzman yok</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Sohbetle Uzman Oluştur seçeneğiyle ihtiyacınızı doğal dille anlatabilirsiniz.
              </p>
            </div>
          ) : (
            <div className="divide-y border-y">
              {specialists.map((specialist) => (
                <div key={specialist.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                      <Bot className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{specialist.name}</p>
                        <Badge variant={specialist.is_active ? 'success' : 'secondary'}>
                          {specialist.is_active ? 'Aktif' : 'Pasif'}
                        </Badge>
                      </div>
                      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                        {specialist.description || 'Ana Asistana bağlı özel uzman.'}
                      </p>
                    </div>
                  </div>
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/dashboard/bots/${specialist.id}/knowledge`}>
                      <BookOpen className="mr-2 h-4 w-4" />Bilgileri Düzenle
                    </Link>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </section>

        <Dialog open={trainingOpen} onOpenChange={setTrainingOpen}>
          <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
            <DialogHeader><DialogTitle>Ana Asistanı Eğit</DialogTitle><DialogDescription>İşletmenize uygun seçenekleri seçin. Sistem teknik talimatları kendisi oluşturur.</DialogDescription></DialogHeader>
            <div className="space-y-6 py-2">
              <ChoiceGroup label="Asistanın ana amacı" value={training.goal} options={trainingOptions.goal} onChange={(value) => setTraining({ ...training, goal: value as Training['goal'] })} />
              <ChoiceGroup label="Konuşma tonu" value={training.tone} options={trainingOptions.tone} onChange={(value) => setTraining({ ...training, tone: value as Training['tone'] })} />
              <ChoiceGroup label="Yanıt uzunluğu" value={training.response_length} options={trainingOptions.response_length} onChange={(value) => setTraining({ ...training, response_length: value as Training['response_length'] })} />
              <ChoiceGroup label="Fiyat yaklaşımı" value={training.price_policy} options={trainingOptions.price_policy} onChange={(value) => setTraining({ ...training, price_policy: value as Training['price_policy'] })} />
              <ChoiceGroup label="İnsan desteğine devir" value={training.handoff_mode} options={trainingOptions.handoff_mode} onChange={(value) => setTraining({ ...training, handoff_mode: value as Training['handoff_mode'] })} />
              <div className="space-y-2"><Label htmlFor="business-summary">İşletmeyi bir cümleyle anlatın</Label><Textarea id="business-summary" value={training.business_summary} onChange={(event) => setTraining({ ...training, business_summary: event.target.value })} maxLength={3000} className="min-h-24" placeholder="Örn: Hafta içi 09.00-18.00 arasında bireysel diyet danışmanlığı sunuyoruz." /></div>
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setTrainingOpen(false)}>İptal</Button><Button onClick={() => trainingMutation.mutate(training)} disabled={trainingMutation.isPending}>{trainingMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}Kaydet ve Eğit</Button></DialogFooter>
          </DialogContent>
        </Dialog>

      </div>
    </ContentContainer>
  )
}
