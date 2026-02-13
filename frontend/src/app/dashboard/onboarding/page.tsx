'use client'

import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import {
  CheckCircle2,
  Circle,
  ArrowRight,
  Sparkles,
  Bot,
  MessageSquare,
  BookOpen,
  Smartphone,
  Zap,
  X,
  Loader2
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { setupOnboardingApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'

interface OnboardingStep {
  key: string
  title: string
  description: string
  order: number
  required: boolean
  completed: boolean
  completed_at: string | null
  is_current: boolean
}

interface OnboardingStatus {
  is_completed: boolean
  completed_at: string | null
  current_step: string
  progress_percentage: number
  dismissed: boolean
  steps: OnboardingStep[]
}

const stepIcons: Record<string, React.ElementType> = {
  create_tenant: Sparkles,
  create_bot: Bot,
  add_welcome_message: MessageSquare,
  add_knowledge: BookOpen,
  connect_whatsapp: Smartphone,
  activate_bot: Zap,
}

const stepUrls: Record<string, string> = {
  create_tenant: '/dashboard/settings',
  create_bot: '/dashboard/bots',
  add_welcome_message: '/dashboard/bots',
  add_knowledge: '/dashboard/bots',
  connect_whatsapp: '/dashboard/setup/whatsapp',
  activate_bot: '/dashboard/bots',
}

export default function OnboardingPage() {
  const router = useRouter()
  const queryClient = useQueryClient()

  const { data: status, isLoading, refetch } = useQuery<OnboardingStatus>({
    queryKey: ['onboarding-status'],
    queryFn: () => setupOnboardingApi.getStatus().then(res => res.data),
  })

  const checkProgressMutation = useMutation({
    mutationFn: () => setupOnboardingApi.checkProgress(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['onboarding-status'] })
    },
  })

  const dismissMutation = useMutation({
    mutationFn: () => setupOnboardingApi.dismiss(),
    onSuccess: () => {
      router.push('/dashboard')
    },
  })

  useEffect(() => {
    // Auto-check progress on mount
    checkProgressMutation.mutate()
  }, [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (status?.is_completed) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card className="border-green-200 dark:border-green-800 animate-scale-in">
          <CardContent className="p-12 text-center">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-green-400 to-emerald-600 flex items-center justify-center animate-breathe shadow-lg shadow-green-500/30">
              <CheckCircle2 className="w-10 h-10 text-white" />
            </div>
            <h2 className="text-2xl font-bold mb-2 gradient-text-vivid">Tebrikler! 🎉</h2>
            <p className="text-muted-foreground mb-6">
              Kurulumunuz tamamlandı. Botunuz artık müşterilerinize hizmet vermeye hazır!
            </p>
            <Button
              onClick={() => router.push('/dashboard')}
              className="bg-gradient-to-r from-green-600 to-emerald-600"
            >
              Dashboard'a Git
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const currentStep = status?.steps.find(s => s.is_current)

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Kurulum Sihirbazı"
          description="Botunuzu adım adım kurun ve hemen kullanmaya başlayın."
          actions={(
            <Button variant="ghost" onClick={() => dismissMutation.mutate()} className="text-muted-foreground">
              <X className="w-4 h-4 mr-2" />
              Daha Sonra
            </Button>
          )}
        />

        {/* Progress Bar */}
        <Card className="glass-card animate-slide-up">
          <CardContent className="p-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium">İlerleme</span>
              <Badge variant="secondary" className="text-lg px-3 font-bold">
                %{status?.progress_percentage || 0}
              </Badge>
            </div>
            <div className="w-full h-3 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden shadow-inner">
              <div
                className="h-full bg-gradient-to-r from-blue-500 via-violet-500 to-purple-600 transition-all duration-700 animate-gradient-x rounded-full"
                style={{ width: `${status?.progress_percentage || 0}%` }}
              />
            </div>
          </CardContent>
        </Card>

        {/* Steps */}
        <div className="space-y-4">
          {status?.steps.map((step, index) => {
            const Icon = stepIcons[step.key] || Circle
            const isCompleted = step.completed
            const isCurrent = step.is_current
            const isLocked = !isCompleted && !isCurrent && index > (status.steps.findIndex(s => s.is_current) || 0)

            return (
              <Card
                key={step.key}
                className={cn(
                  'transition-all duration-300 card-hover-lift animate-fade-in-up',
                  isCurrent && 'ring-2 ring-blue-500 shadow-glow-primary gradient-border-animated',
                  isCompleted && 'opacity-70',
                  isLocked && 'opacity-50'
                )}
                style={{ animationDelay: `${index * 80}ms` }}
              >
                <CardContent className="p-6">
                  <div className="flex items-center gap-4">
                    {/* Step Number/Icon */}
                    <div className={cn(
                      'w-12 h-12 rounded-xl flex items-center justify-center shrink-0',
                      isCompleted
                        ? 'bg-green-100 dark:bg-green-900/30'
                        : isCurrent
                          ? 'bg-gradient-to-br from-blue-500 to-violet-600'
                          : 'bg-slate-100 dark:bg-slate-800'
                    )}>
                      {isCompleted ? (
                        <CheckCircle2 className="w-6 h-6 text-green-600" />
                      ) : (
                        <Icon className={cn(
                          'w-6 h-6',
                          isCurrent ? 'text-white' : 'text-slate-400'
                        )} />
                      )}
                    </div>

                    {/* Step Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{step.title}</h3>
                        {!step.required && (
                          <Badge variant="outline" className="text-xs">Opsiyonel</Badge>
                        )}
                        {isCompleted && (
                          <Badge variant="success" className="text-xs">Tamamlandı</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {step.description}
                      </p>
                    </div>

                    {/* Action Button */}
                    <div className="shrink-0">
                      {isCurrent && !isCompleted ? (
                        <Button
                          onClick={() => router.push(stepUrls[step.key])}
                          className="bg-gradient-to-r from-blue-600 to-violet-600"
                        >
                          Başla
                          <ArrowRight className="w-4 h-4 ml-2" />
                        </Button>
                      ) : isCompleted ? (
                        <Button
                          variant="outline"
                          onClick={() => router.push(stepUrls[step.key])}
                        >
                          Düzenle
                        </Button>
                      ) : !step.required && !isLocked ? (
                        <Button
                          variant="ghost"
                          onClick={() => router.push(stepUrls[step.key])}
                        >
                          Atla
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* Help Section */}
        <Card className="bg-gradient-to-r from-blue-50 to-violet-50 dark:from-blue-900/20 dark:to-violet-900/20 border-blue-200 dark:border-blue-800 glass-card">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                <Sparkles className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h4 className="font-semibold mb-1">Yardıma mı ihtiyacınız var?</h4>
                <p className="text-sm text-muted-foreground mb-3">
                  Kurulum sürecinde herhangi bir sorunla karşılaşırsanız, destek ekibimizle iletişime geçebilirsiniz.
                </p>
                <Button variant="outline" size="sm">
                  Destek Al
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </ContentContainer>
  )
}
