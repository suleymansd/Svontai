'use client'

import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import {
  ArrowLeft,
  Check,
  Circle,
  Loader2,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Smartphone,
  Shield,
  Zap,
  MessageSquare,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Clock,
  HelpCircle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

// Types
interface OnboardingStep {
  step_key: string
  step_order: number
  step_name: string
  step_description: string | null
  status: 'pending' | 'in_progress' | 'done' | 'error' | 'skipped'
  message: string | null
  started_at: string | null
  completed_at: string | null
  updated_at: string
}

interface OnboardingStatus {
  steps: OnboardingStep[]
  current_step: string | null
  is_complete: boolean
  whatsapp_connected: boolean
  phone_number: string | null
}

interface StartResponse {
  oauth_url: string
  embedded_config: any
  verify_token: string
  state: string
  webhook_url: string
}

// Step icons
const stepIcons: Record<string, React.ElementType> = {
  start_setup: Zap,
  meta_auth: Shield,
  select_waba: Smartphone,
  save_credentials: Check,
  configure_webhook: MessageSquare,
  verify_webhook: Clock,
  complete: CheckCircle2
}

// Status colors and icons
const statusConfig = {
  pending: { color: 'text-slate-400', bg: 'bg-slate-100 dark:bg-slate-800', icon: Circle },
  in_progress: { color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', icon: Loader2, animate: true },
  done: { color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30', icon: CheckCircle2 },
  error: { color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', icon: XCircle },
  skipped: { color: 'text-slate-400', bg: 'bg-slate-100 dark:bg-slate-800', icon: Circle }
}

export default function WhatsAppSetupPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [isConnecting, setIsConnecting] = useState(false)
  const [pollInterval, setPollInterval] = useState<number | false>(false)
  const popupRef = useRef<Window | null>(null)
  const popupCheckRef = useRef<number | null>(null)

  // Fetch onboarding status
  const { data: status, isLoading, refetch } = useQuery<OnboardingStatus>({
    queryKey: ['whatsapp-onboarding-status'],
    queryFn: () => api.get('/api/onboarding/whatsapp/status').then(res => res.data),
    refetchInterval: pollInterval,
  })

  // Start onboarding mutation
  const startMutation = useMutation({
    mutationFn: () => api.post('/api/onboarding/whatsapp/start').then(res => res.data as StartResponse),
    onSuccess: (data) => {
      // Start polling
      setPollInterval(2000)

      // Open Meta OAuth in popup
      const width = 600
      const height = 700
      const left = window.screenX + (window.outerWidth - width) / 2
      const top = window.screenY + (window.outerHeight - height) / 2

      const popup = window.open(
        data.oauth_url,
        'whatsapp_connect',
        `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`
      )

      if (popup) {
        popupRef.current = popup
        setIsConnecting(true)

        if (popupCheckRef.current) {
          window.clearInterval(popupCheckRef.current)
        }
        popupCheckRef.current = window.setInterval(() => {
          if (popupRef.current && popupRef.current.closed) {
            popupRef.current = null
            if (popupCheckRef.current) {
              window.clearInterval(popupCheckRef.current)
              popupCheckRef.current = null
            }
            setIsConnecting(false)
            refetch()
          }
        }, 500)
      } else {
        toast({
          title: 'Pop-up engellendi',
          description: 'Tarayıcı pop-up engelini kapatın veya yeni sekmede devam edin.',
          variant: 'destructive',
        })
        window.location.assign(data.oauth_url)
      }
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Kurulum başlatılamadı',
        variant: 'destructive',
      })
    }
  })

  // Reset mutation
  const resetMutation = useMutation({
    mutationFn: () => api.post('/api/onboarding/whatsapp/reset'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-onboarding-status'] })
      toast({
        title: 'Sıfırlandı',
        description: 'WhatsApp kurulumu sıfırlandı.',
      })
    }
  })

  // Retry step mutation
  const retryMutation = useMutation({
    mutationFn: (stepKey: string) => api.post(`/api/onboarding/whatsapp/retry-step/${stepKey}`),
    onSuccess: () => {
      refetch()
    }
  })

  // Stop polling when complete
  useEffect(() => {
    if (status?.is_complete) {
      setPollInterval(false)
    }
  }, [status?.is_complete])

  // Check URL params for success
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('success') === 'true') {
      toast({
        title: 'Bağlantı Başarılı!',
        description: 'WhatsApp hesabınız başarıyla bağlandı.',
      })
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type !== 'WHATSAPP_CONNECTED') return

      if (popupRef.current && !popupRef.current.closed) {
        popupRef.current.close()
      }
      popupRef.current = null
      if (popupCheckRef.current) {
        window.clearInterval(popupCheckRef.current)
        popupCheckRef.current = null
      }

      setIsConnecting(false)
      refetch()

      if (event.data?.success) {
        toast({
          title: 'Bağlantı Başarılı!',
          description: 'WhatsApp hesabınız bağlandı.',
        })
      } else {
        toast({
          title: 'Bağlantı Başarısız',
          description: event.data?.error || 'Meta bağlantısı tamamlanamadı.',
          variant: 'destructive',
        })
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [refetch, toast])

  useEffect(() => {
    return () => {
      if (popupCheckRef.current) {
        window.clearInterval(popupCheckRef.current)
        popupCheckRef.current = null
      }
      popupRef.current = null
    }
  }, [])

  const currentStepIndex = status?.steps.findIndex(s => s.step_key === status.current_step) ?? -1
  const progressPercent = status?.steps
    ? (status.steps.filter(s => s.status === 'done').length / status.steps.length) * 100
    : 0

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-green-500 flex items-center justify-center">
                <Smartphone className="w-5 h-5 text-white" />
              </div>
              WhatsApp Kurulumu
            </h1>
            <p className="text-muted-foreground mt-1">
              WhatsApp Business hesabınızı 1-3 dakikada bağlayın
            </p>
          </div>
        </div>
        <Link href="/dashboard/help/whatsapp-setup">
          <Button variant="outline" size="sm">
            <HelpCircle className="w-4 h-4 mr-2" />
            Yardım
          </Button>
        </Link>
      </div>

      {/* Status Card */}
      {status?.whatsapp_connected && (
        <Card className="border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center">
                  <CheckCircle2 className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-green-800 dark:text-green-200">
                    WhatsApp Bağlı!
                  </h3>
                  <p className="text-green-600 dark:text-green-400">
                    {status.phone_number || 'Telefon numarası'}
                  </p>
                </div>
              </div>
              <Button variant="outline" onClick={() => resetMutation.mutate()}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Yeniden Kur
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Progress Bar */}
      {!status?.is_complete && status?.steps && status.steps.length > 0 && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">İlerleme</span>
            <span className="font-medium">{Math.round(progressPercent)}%</span>
          </div>
          <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green-500 to-emerald-500 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Steps */}
      <Card>
        <CardHeader>
          <CardTitle>Kurulum Adımları</CardTitle>
          <CardDescription>
            Her adım otomatik olarak tamamlanır, sadece Meta ile giriş yapmanız yeterli
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : !status?.steps || status.steps.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-20 h-20 mx-auto rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
                <Smartphone className="w-10 h-10 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">WhatsApp'ı Bağlayın</h3>
              <p className="text-muted-foreground max-w-md mx-auto mb-6">
                WhatsApp Business hesabınızı bağlayarak müşterilerinize WhatsApp üzerinden
                7/24 otomatik yanıt vermeye başlayın.
              </p>
              <Button
                size="lg"
                className="bg-green-600 hover:bg-green-700"
                onClick={() => startMutation.mutate()}
                disabled={startMutation.isPending || isConnecting}
              >
                {startMutation.isPending || isConnecting ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    Bağlanıyor...
                  </>
                ) : (
                  <>
                    <Smartphone className="w-5 h-5 mr-2" />
                    WhatsApp'ı Bağla
                  </>
                )}
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {status.steps.map((step, index) => {
                const Icon = stepIcons[step.step_key] || Circle
                const config = statusConfig[step.status]
                const StatusIcon = config.icon
                const isActive = step.step_key === status.current_step
                const isPast = index < currentStepIndex

                return (
                  <div
                    key={step.step_key}
                    className={cn(
                      'flex items-start gap-4 p-4 rounded-xl transition-all',
                      isActive && 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800',
                      step.status === 'done' && 'bg-green-50/50 dark:bg-green-900/10',
                      step.status === 'error' && 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                    )}
                  >
                    {/* Step Number/Status */}
                    <div className={cn(
                      'w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0',
                      config.bg
                    )}>
                      <StatusIcon className={cn(
                        'w-5 h-5',
                        config.color,
                        (config as any).animate && 'animate-spin'
                      )} />
                    </div>

                    {/* Step Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium">{step.step_name}</h4>
                        {step.status === 'done' && (
                          <Badge variant="success" className="text-xs">Tamamlandı</Badge>
                        )}
                        {step.status === 'in_progress' && (
                          <Badge className="text-xs bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                            Devam Ediyor
                          </Badge>
                        )}
                        {step.status === 'error' && (
                          <Badge variant="destructive" className="text-xs">Hata</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {step.message || step.step_description}
                      </p>

                      {/* Error retry button */}
                      {step.status === 'error' && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-2"
                          onClick={() => retryMutation.mutate(step.step_key)}
                        >
                          <RefreshCw className="w-3 h-3 mr-2" />
                          Tekrar Dene
                        </Button>
                      )}
                    </div>

                    {/* Step Icon */}
                    <div className={cn(
                      'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
                      step.status === 'done' ? 'bg-green-100 dark:bg-green-900/30' : 'bg-slate-100 dark:bg-slate-800'
                    )}>
                      <Icon className={cn(
                        'w-5 h-5',
                        step.status === 'done' ? 'text-green-600' : 'text-slate-500'
                      )} />
                    </div>
                  </div>
                )
              })}

              {/* Action Button */}
              {!status.is_complete && !isConnecting && (
                <div className="pt-4 border-t">
                  <Button
                    className="w-full bg-green-600 hover:bg-green-700"
                    size="lg"
                    onClick={() => startMutation.mutate()}
                    disabled={startMutation.isPending}
                  >
                    {startMutation.isPending ? (
                      <>
                        <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                        Başlatılıyor...
                      </>
                    ) : currentStepIndex > 0 ? (
                      <>
                        <RefreshCw className="w-5 h-5 mr-2" />
                        Devam Et
                      </>
                    ) : (
                      <>
                        <Smartphone className="w-5 h-5 mr-2" />
                        WhatsApp'ı Bağla
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Cards */}
      <div className="grid md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-4">
              <Clock className="w-5 h-5 text-blue-600" />
            </div>
            <h3 className="font-semibold mb-2">1-3 Dakika</h3>
            <p className="text-sm text-muted-foreground">
              Kurulum sadece birkaç dakika sürer. Meta hesabınızla giriş yapın, biz gerisini hallederiz.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
              <Shield className="w-5 h-5 text-green-600" />
            </div>
            <h3 className="font-semibold mb-2">Güvenli Bağlantı</h3>
            <p className="text-sm text-muted-foreground">
              Meta'nın resmi Embedded Signup yöntemini kullanıyoruz. Verileriniz şifreli ve güvende.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="w-10 h-10 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center mb-4">
              <Zap className="w-5 h-5 text-violet-600" />
            </div>
            <h3 className="font-semibold mb-2">Otomatik Kurulum</h3>
            <p className="text-sm text-muted-foreground">
              Webhook, token ve diğer tüm ayarlar otomatik yapılandırılır.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Requirements */}
      <Card>
        <CardHeader>
          <CardTitle>Gereksinimler</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {[
              'Meta (Facebook) Business hesabı',
              'WhatsApp Business hesabı veya numara',
              'İşletme doğrulaması (Meta Business Suite\'de)',
              'Aktif telefon numarası (WhatsApp Web\'de kullanılmayan)'
            ].map((item, i) => (
              <li key={i} className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center flex-shrink-0">
                  <Check className="w-3 h-3 text-green-600" />
                </div>
                <span className="text-sm">{item}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
