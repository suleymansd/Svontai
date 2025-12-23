'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Check, 
  Sparkles,
  Zap,
  Crown,
  Building2,
  Loader2,
  CreditCard,
  Calendar,
  AlertCircle
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { subscriptionApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'

interface Plan {
  id: string
  name: string
  display_name: string
  description: string | null
  plan_type: string
  price_monthly: number
  price_yearly: number
  currency: string
  message_limit: number
  bot_limit: number
  knowledge_items_limit: number
  feature_flags: Record<string, boolean>
  trial_days: number
}

interface Subscription {
  id: string
  plan_name: string
  plan_display_name: string
  status: string
  started_at: string
  trial_ends_at: string | null
  current_period_end: string | null
  messages_used: number
  message_limit: number
}

const planIcons: Record<string, React.ElementType> = {
  free: Sparkles,
  starter: Zap,
  pro: Crown,
  business: Building2,
}

const planColors: Record<string, string> = {
  free: 'from-slate-500 to-slate-600',
  starter: 'from-blue-500 to-cyan-500',
  pro: 'from-violet-500 to-purple-600',
  business: 'from-amber-500 to-orange-500',
}

const featureLabels: Record<string, string> = {
  whatsapp_integration: 'WhatsApp Entegrasyonu',
  analytics: 'Detaylı Analitikler',
  custom_branding: 'Özel Markalama',
  priority_support: 'Öncelikli Destek',
  api_access: 'API Erişimi',
  export_data: 'Veri Dışa Aktarma',
  operator_takeover: 'Operatör Devralma',
  lead_automation: 'Otomatik Lead Yakalama',
  white_label: 'White Label',
  dedicated_support: 'Özel Müşteri Temsilcisi',
}

export default function BillingPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  
  const { data: plans, isLoading: plansLoading } = useQuery<Plan[]>({
    queryKey: ['plans'],
    queryFn: () => subscriptionApi.listPlans().then(res => res.data),
  })
  
  const { data: subscription, isLoading: subscriptionLoading } = useQuery<Subscription>({
    queryKey: ['subscription'],
    queryFn: () => subscriptionApi.getCurrentSubscription().then(res => res.data),
  })
  
  const upgradeMutation = useMutation({
    mutationFn: (planName: string) => subscriptionApi.upgrade(planName),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['subscription'] })
      toast({
        title: 'Başarılı!',
        description: data.data.message,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Bir hata oluştu',
        variant: 'destructive',
      })
    },
  })
  
  const isLoading = plansLoading || subscriptionLoading
  
  const currentPlanIndex = plans?.findIndex(p => p.name === subscription?.plan_name) ?? -1
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Abonelik & Faturalandırma 💳</h1>
        <p className="text-muted-foreground mt-1">
          Planınızı yönetin ve özelliklerinizi genişletin
        </p>
      </div>
      
      {/* Current Plan Status */}
      {subscription && (
        <Card className="border-blue-200 dark:border-blue-800 bg-gradient-to-r from-blue-50 to-violet-50 dark:from-blue-900/20 dark:to-violet-900/20">
          <CardContent className="p-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant={subscription.status === 'trial' ? 'warning' : 'success'}>
                    {subscription.status === 'trial' ? 'Deneme Süresi' : 
                     subscription.status === 'active' ? 'Aktif' : 
                     subscription.status}
                  </Badge>
                  <span className="text-lg font-semibold">{subscription.plan_display_name} Plan</span>
                </div>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <CreditCard className="w-4 h-4" />
                    {subscription.messages_used} / {subscription.message_limit} mesaj
                  </span>
                  {subscription.trial_ends_at && (
                    <span className="flex items-center gap-1">
                      <Calendar className="w-4 h-4" />
                      Deneme bitiş: {new Date(subscription.trial_ends_at).toLocaleDateString('tr-TR')}
                    </span>
                  )}
                </div>
              </div>
              <div>
                <div className="w-full sm:w-48 h-2 bg-white dark:bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-blue-500 to-violet-600"
                    style={{ width: `${(subscription.messages_used / subscription.message_limit) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1 text-right">
                  %{Math.round((subscription.messages_used / subscription.message_limit) * 100)} kullanıldı
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Plans Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          [...Array(4)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="h-40 bg-slate-100 dark:bg-slate-800 rounded-xl" />
              </CardContent>
            </Card>
          ))
        ) : (
          plans?.map((plan, index) => {
            const Icon = planIcons[plan.name] || Sparkles
            const isCurrentPlan = subscription?.plan_name === plan.name
            const isUpgrade = index > currentPlanIndex
            const isDowngrade = index < currentPlanIndex
            
            return (
              <Card 
                key={plan.id}
                className={cn(
                  'relative overflow-hidden transition-all duration-300',
                  isCurrentPlan && 'ring-2 ring-blue-500 shadow-lg',
                  plan.name === 'pro' && 'border-violet-300 dark:border-violet-700'
                )}
              >
                {plan.name === 'pro' && (
                  <div className="absolute top-0 right-0 bg-gradient-to-r from-violet-500 to-purple-600 text-white text-xs px-3 py-1 rounded-bl-lg">
                    Popüler
                  </div>
                )}
                
                <CardHeader className="pb-4">
                  <div className={cn(
                    'w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center mb-3',
                    planColors[plan.name]
                  )}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <CardTitle>{plan.display_name}</CardTitle>
                  <CardDescription>{plan.description}</CardDescription>
                </CardHeader>
                
                <CardContent className="space-y-4">
                  {/* Price */}
                  <div>
                    <span className="text-3xl font-bold">
                      {plan.price_monthly === 0 ? 'Ücretsiz' : `₺${plan.price_monthly}`}
                    </span>
                    {plan.price_monthly > 0 && (
                      <span className="text-muted-foreground">/ay</span>
                    )}
                  </div>
                  
                  {/* Limits */}
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Mesaj limiti</span>
                      <span className="font-medium">{plan.message_limit.toLocaleString()}/ay</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Bot limiti</span>
                      <span className="font-medium">{plan.bot_limit}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Bilgi tabanı</span>
                      <span className="font-medium">{plan.knowledge_items_limit}</span>
                    </div>
                  </div>
                  
                  {/* Features */}
                  <div className="pt-4 border-t space-y-2">
                    {Object.entries(plan.feature_flags).slice(0, 5).map(([key, enabled]) => (
                      <div key={key} className="flex items-center gap-2 text-sm">
                        <Check className={cn(
                          'w-4 h-4',
                          enabled ? 'text-green-500' : 'text-slate-300 dark:text-slate-600'
                        )} />
                        <span className={cn(
                          !enabled && 'text-muted-foreground line-through'
                        )}>
                          {featureLabels[key] || key}
                        </span>
                      </div>
                    ))}
                  </div>
                  
                  {/* Action Button */}
                  <Button 
                    className={cn(
                      'w-full',
                      isCurrentPlan 
                        ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100'
                        : plan.name === 'pro'
                          ? 'bg-gradient-to-r from-violet-600 to-purple-600'
                          : ''
                    )}
                    variant={isCurrentPlan ? 'secondary' : isDowngrade ? 'outline' : 'default'}
                    disabled={isCurrentPlan || upgradeMutation.isPending}
                    onClick={() => upgradeMutation.mutate(plan.name)}
                  >
                    {upgradeMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : isCurrentPlan ? (
                      'Mevcut Plan'
                    ) : isUpgrade ? (
                      'Yükselt'
                    ) : (
                      'Düşür'
                    )}
                  </Button>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>
      
      {/* Payment Note */}
      <Card className="bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800">
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-amber-900 dark:text-amber-100">Ödeme Entegrasyonu</h4>
              <p className="text-sm text-amber-700 dark:text-amber-200 mt-1">
                Ödeme sistemi yakında aktif olacaktır. Şu anda deneme amaçlı tüm planları ücretsiz kullanabilirsiniz.
                Gerçek ödeme için Stripe, Iyzico veya PayTR entegrasyonu eklenecektir.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* FAQ */}
      <Card>
        <CardHeader>
          <CardTitle>Sık Sorulan Sorular</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="font-medium mb-1">Planımı dilediğim zaman değiştirebilir miyim?</h4>
            <p className="text-sm text-muted-foreground">
              Evet, planınızı istediğiniz zaman yükseltebilir veya düşürebilirsiniz. Değişiklikler anında uygulanır.
            </p>
          </div>
          <div>
            <h4 className="font-medium mb-1">Mesaj limitimi aşarsam ne olur?</h4>
            <p className="text-sm text-muted-foreground">
              Mesaj limitinize ulaştığınızda botlarınız yanıt veremez. Planınızı yükseltebilir veya sonraki ayı bekleyebilirsiniz.
            </p>
          </div>
          <div>
            <h4 className="font-medium mb-1">Deneme süresi ne kadar?</h4>
            <p className="text-sm text-muted-foreground">
              Ücretli planlar için 14 günlük ücretsiz deneme süresi sunuyoruz. Bu sürede tüm özellikleri test edebilirsiniz.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

