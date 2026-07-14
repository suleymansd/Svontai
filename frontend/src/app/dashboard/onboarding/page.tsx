'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowRight,
  Bot,
  Building2,
  CheckCircle2,
  ExternalLink,
  LinkIcon,
  Loader2,
  MessageSquare,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  Users,
} from 'lucide-react'
import { onboardingApi, setupOnboardingApi } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'

const industries = [
  { value: 'real_estate', label: 'Emlak' },
  { value: 'clinic', label: 'Klinik / Sağlık' },
  { value: 'restaurant', label: 'Restoran' },
  { value: 'education', label: 'Eğitim' },
  { value: 'service', label: 'Hizmet İşletmesi' },
  { value: 'ecommerce', label: 'E-ticaret' },
  { value: 'other', label: 'Diğer' },
]

const goals = [
  { value: 'info', label: 'Bilgi almak' },
  { value: 'appointment', label: 'Randevu almak' },
  { value: 'price', label: 'Fiyat sormak' },
  { value: 'support', label: 'Destek istemek' },
  { value: 'sales', label: 'Ürün / ilan sormak' },
]

const tones = [
  { value: 'professional', label: 'Profesyonel' },
  { value: 'friendly', label: 'Samimi' },
  { value: 'short', label: 'Kısa ve net' },
  { value: 'sales', label: 'Satış odaklı' },
]

const handoffRules = [
  { value: 'complaint', label: 'Şikayet gelirse' },
  { value: 'price_negotiation', label: 'Fiyat pazarlığı olursa' },
  { value: 'appointment_confirmed', label: 'Randevu kesinleşirse' },
  { value: 'unknown_question', label: 'Cevap bilinmiyorsa' },
]

export default function OnboardingPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const popupRef = useRef<Window | null>(null)
  const hydratedFromStatusRef = useRef(false)
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    setup_mode: 'concierge' as 'concierge' | 'self_serve',
    industry: '',
    primary_goal: '',
    tone: 'professional',
    handoff_rules: [] as string[],
    website_url: '',
    instagram_url: '',
    business_summary: '',
  })

  const statusQuery = useQuery({
    queryKey: ['onboarding-status'],
    queryFn: () => setupOnboardingApi.getStatus().then(res => res.data),
  })
  const whatsappQuery = useQuery({
    queryKey: ['whatsapp-onboarding-status'],
    queryFn: () => onboardingApi.getWhatsAppStatus().then(res => res.data),
  })

  const saveProfileMutation = useMutation({
    mutationFn: () => setupOnboardingApi.saveBusinessProfile(form).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['onboarding-status'] })
      setStep(4)
    },
    onError: (error: any) => {
      toast({
        title: 'Bilgiler kaydedilemedi',
        description: error.response?.data?.detail || 'Lütfen tekrar deneyin.',
        variant: 'destructive',
      })
    },
  })

  const startWhatsAppMutation = useMutation({
    mutationFn: () => onboardingApi.startWhatsApp().then(res => res.data),
    onSuccess: (data) => {
      const popup = window.open(
        data.oauth_url,
        'whatsapp_connect',
        'width=600,height=700,toolbar=no,menubar=no'
      )
      if (popup) {
        popupRef.current = popup
      } else {
        window.location.assign(data.oauth_url)
      }
    },
    onError: (error: any) => {
      toast({
        title: 'WhatsApp bağlantısı başlatılamadı',
        description: error.response?.data?.detail || 'Meta ayarları hazır değilse bu adımı sonra tamamlayabilirsiniz.',
        variant: 'destructive',
      })
    },
  })

  const runAutopilotMutation = useMutation({
    mutationFn: () => setupOnboardingApi.runAutopilot().then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['onboarding-status'] })
      queryClient.invalidateQueries({ queryKey: ['autopilot-status'] })
      queryClient.invalidateQueries({ queryKey: ['bots'] })
      setStep(5)
    },
    onError: (error: any) => {
      toast({
        title: 'Kurulum başlatılamadı',
        description: error.response?.data?.detail || 'Lütfen tekrar deneyin.',
        variant: 'destructive',
      })
    },
  })

  const progress = useMemo(() => {
    if (statusQuery.data?.is_completed) return 100
    return Math.max(statusQuery.data?.progress_percentage || 20, Math.round(((step + 1) / 6) * 100))
  }, [statusQuery.data, step])

  const toggleHandoff = (value: string) => {
    setForm((current) => ({
      ...current,
      handoff_rules: current.handoff_rules.includes(value)
        ? current.handoff_rules.filter(item => item !== value)
        : [...current.handoff_rules, value],
    }))
  }

  const canContinueProfile = form.industry && form.primary_goal && form.tone
  const whatsappConnected = whatsappQuery.data?.whatsapp_connected

  useEffect(() => {
    if (!statusQuery.data) return
    if (statusQuery.data.is_completed) {
      setStep(5)
      return
    }
    if (hydratedFromStatusRef.current) return
    hydratedFromStatusRef.current = true
    const current = statusQuery.data.current_step
    const nextStepByKey: Record<string, number> = {
      business_profile: 0,
      customer_goals: 1,
      knowledge_sources: 3,
      connect_whatsapp: 4,
      autopilot_setup: 5,
      review_ready: 5,
    }
    if (current && current in nextStepByKey) {
      setStep(nextStepByKey[current])
    }
  }, [statusQuery.data])

  return (
    <ContentContainer>
      <div className="mx-auto max-w-5xl space-y-8">
        <PageHeader
          title="SmartWA Kurulum Merkezi"
          description="Hızlı kurulum yapın veya bilgi formasyonunu ekibimize bırakın; sisteminiz güvenli otonomiyle hazırlansın."
          icon={<ShieldCheck className="h-7 w-7 text-primary" />}
        />

        <Card className="border-border/70">
          <CardContent className="p-5">
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="font-medium">Kurulum ilerlemesi</span>
              <span className="text-muted-foreground">%{progress}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-violet-500" style={{ width: `${progress}%` }} />
            </div>
          </CardContent>
        </Card>

        {step === 0 && (
          <Card>
            <CardHeader>
              <CardTitle>1. İşletmenizi tanıyalım</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <Label>Kurulum şekli</Label>
                <div className="grid gap-3 md:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, setup_mode: 'concierge' })}
                    className={`rounded-xl border p-4 text-left transition ${form.setup_mode === 'concierge' ? 'border-primary bg-primary/10' : 'hover:bg-muted/50'}`}
                  >
                    <ShieldCheck className="mb-2 h-5 w-5 text-primary" />
                    <span className="font-medium">Biz Kuralım</span>
                    <p className="mt-1 text-sm text-muted-foreground">Minimum bilgi verin; işletme bilgi formasyonunu ekibimiz hazırlasın.</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, setup_mode: 'self_serve' })}
                    className={`rounded-xl border p-4 text-left transition ${form.setup_mode === 'self_serve' ? 'border-primary bg-primary/10' : 'hover:bg-muted/50'}`}
                  >
                    <RefreshCw className="mb-2 h-5 w-5 text-primary" />
                    <span className="font-medium">Hızlı Kurulum</span>
                    <p className="mt-1 text-sm text-muted-foreground">Cevaplarınızla botu ve kurulum ayarlarını hemen hazırlayın.</p>
                  </button>
                </div>
              </div>
              <div className="space-y-3">
                <Label>Sektörünüz</Label>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {industries.map(item => (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => setForm({ ...form, industry: item.value })}
                      className={`rounded-xl border p-4 text-left transition ${form.industry === item.value ? 'border-primary bg-primary/10' : 'hover:bg-muted/50'}`}
                    >
                      <Building2 className="mb-2 h-5 w-5 text-primary" />
                      <span className="font-medium">{item.label}</span>
                    </button>
                  ))}
                </div>
              </div>
              <Button disabled={!form.industry} onClick={() => setStep(1)}>
                Devam Et
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        )}

        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>2. Müşteriler size en çok neden yazıyor?</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {goals.map(item => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setForm({ ...form, primary_goal: item.value })}
                    className={`rounded-xl border p-4 text-left transition ${form.primary_goal === item.value ? 'border-primary bg-primary/10' : 'hover:bg-muted/50'}`}
                  >
                    <MessageSquare className="mb-2 h-5 w-5 text-primary" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep(0)}>Geri</Button>
                <Button disabled={!form.primary_goal} onClick={() => setStep(2)}>Devam Et</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 2 && (
          <Card>
            <CardHeader>
              <CardTitle>3. Yanıt tarzı ve insan devri</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <Label>Botunuzun tonu</Label>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {tones.map(item => (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => setForm({ ...form, tone: item.value })}
                      className={`rounded-xl border p-4 text-left transition ${form.tone === item.value ? 'border-primary bg-primary/10' : 'hover:bg-muted/50'}`}
                    >
                      <Bot className="mb-2 h-5 w-5 text-primary" />
                      <span className="font-medium">{item.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <Label>Ne zaman insan devreye girsin?</Label>
                <div className="grid gap-3 sm:grid-cols-2">
                  {handoffRules.map(item => (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => toggleHandoff(item.value)}
                      className={`rounded-xl border p-4 text-left transition ${form.handoff_rules.includes(item.value) ? 'border-primary bg-primary/10' : 'hover:bg-muted/50'}`}
                    >
                      <Users className="mb-2 h-5 w-5 text-primary" />
                      <span className="font-medium">{item.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep(1)}>Geri</Button>
                <Button disabled={!canContinueProfile} onClick={() => setStep(3)}>Devam Et</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 3 && (
          <Card>
            <CardHeader>
              <CardTitle>4. Bilgi kaynakları</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <p className="text-sm text-muted-foreground">
                Bu alanlar zorunlu değil. {form.setup_mode === 'concierge' ? 'Ekibimiz işletme bilgi formasyonunu sizin için hazırlayacak.' : 'Boş bırakırsanız sistem güvenli varsayılanlarla başlar ve ekibimiz eksikleri takip eder.'}
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Web sitesi</Label>
                  <div className="relative">
                    <LinkIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input className="pl-9" placeholder="https://..." value={form.website_url} onChange={(e) => setForm({ ...form, website_url: e.target.value })} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Instagram</Label>
                  <div className="relative">
                    <LinkIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input className="pl-9" placeholder="https://instagram.com/..." value={form.instagram_url} onChange={(e) => setForm({ ...form, instagram_url: e.target.value })} />
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Kısa işletme notu</Label>
                <Textarea
                  placeholder="Hangi ürün/hizmetleri veriyorsunuz? Müşteriler en çok ne soruyor?"
                  value={form.business_summary}
                  onChange={(e) => setForm({ ...form, business_summary: e.target.value })}
                />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep(2)}>Geri</Button>
                <Button onClick={() => saveProfileMutation.mutate()} disabled={saveProfileMutation.isPending || !canContinueProfile}>
                  {saveProfileMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Bilgileri Kaydet
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 4 && (
          <Card>
            <CardHeader>
              <CardTitle>5. WhatsApp bağlantısı</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="rounded-xl border p-4">
                <div className="flex items-start gap-3">
                  <Smartphone className="mt-0.5 h-5 w-5 text-primary" />
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold">WhatsApp Business numaranızı bağlayın</h3>
                      <Badge variant={whatsappConnected ? 'success' : 'warning'}>{whatsappConnected ? 'Bağlı' : 'Bekliyor'}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Bağlantı yapılınca sistem mesaj almaya ve yanıt hazırlamaya başlayabilir.
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => startWhatsAppMutation.mutate()} disabled={startWhatsAppMutation.isPending || whatsappConnected}>
                  {startWhatsAppMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ExternalLink className="mr-2 h-4 w-4" />}
                  WhatsApp Bağla
                </Button>
                <Button variant="outline" onClick={() => setStep(5)}>
                  {whatsappConnected ? 'Devam Et' : 'Sonra Bağlayacağım'}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 5 && (
          <Card>
            <CardHeader>
              <CardTitle>6. SmartWA sistemi kursun</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid gap-3 md:grid-cols-3">
                {(form.setup_mode === 'concierge'
                  ? ['Concierge kaydı açılır', 'Bot güvenli modda hazırlanır', 'Sağlık kontrolleri başlar']
                  : ['Bot hazırlanır', 'Bilgi formasyonu açılır', 'Sağlık kontrolleri başlar']
                ).map((item) => (
                  <div key={item} className="rounded-xl border p-4">
                    <CheckCircle2 className="mb-2 h-5 w-5 text-success" />
                    <p className="font-medium">{item}</p>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                {!statusQuery.data?.is_completed ? (
                  <Button onClick={() => runAutopilotMutation.mutate()} disabled={runAutopilotMutation.isPending}>
                    {runAutopilotMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                    SmartWA’yı Kur
                  </Button>
                ) : (
                  <Button asChild>
                    <Link href="/dashboard">Panele Git</Link>
                  </Button>
                )}
                <Button asChild variant="outline">
                  <Link href="/dashboard/bots">Botu Özelleştir</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </ContentContainer>
  )
}
