'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft,
  Save,
  Copy,
  Check,
  MessageSquare,
  Smartphone,
  Globe,
  BookOpen,
  Settings,
  ExternalLink,
  AlertCircle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { botApi, onboardingApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'

export default function BotEditPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const botId = params.botId as string
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<'settings' | 'widget' | 'whatsapp'>('settings')
  const widgetBaseUrl = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_BACKEND_URL || window.location.origin.replace(':3000', ':8000'))
    : (process.env.NEXT_PUBLIC_BACKEND_URL || '')

  const { data: bot, isLoading } = useQuery({
    queryKey: ['bot', botId],
    queryFn: () => botApi.get(botId).then(res => res.data),
  })

  const { data: whatsappAccount } = useQuery({
    queryKey: ['whatsapp-account'],
    queryFn: () => onboardingApi.getWhatsAppAccount().then(res => res.data).catch(() => null),
  })

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    welcome_message: '',
    primary_color: '#3C82F6',
    widget_position: 'right' as 'left' | 'right',
    is_active: true,
  })

  useEffect(() => {
    if (bot) {
      setFormData({
        name: bot.name,
        description: bot.description || '',
        welcome_message: bot.welcome_message,
        primary_color: bot.primary_color,
        widget_position: bot.widget_position,
        is_active: bot.is_active,
      })
    }
  }, [bot])

  const updateMutation = useMutation({
    mutationFn: (data: typeof formData) => botApi.update(botId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bot', botId] })
      queryClient.invalidateQueries({ queryKey: ['bots'] })
      toast({
        title: 'Kaydedildi',
        description: 'Bot ayarları güncellendi.',
      })
    },
  })

  const copyWidgetCode = async () => {
    const code = `<script src="${widgetBaseUrl}/widget.js" data-bot-key="${bot?.public_key}" data-api-url="${widgetBaseUrl}"></script>`
    await navigator.clipboard.writeText(code)
    setCopied(true)
    toast({
      title: 'Kopyalandı',
      description: 'Widget kodu panoya kopyalandı.',
    })
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate(formData)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </div>
    )
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title={bot?.name || 'Bot Detayı'}
          description="Bot ayarlarını düzenleyin."
          actions={(
            <div className="flex gap-2">
              <Link href="/dashboard/bots">
                <Button variant="outline">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Botlara Dön
                </Button>
              </Link>
              <Link href={`/dashboard/bots/${botId}/knowledge`}>
                <Button variant="outline">
                  <BookOpen className="w-4 h-4 mr-2" />
                  AI'ı Eğit
                </Button>
              </Link>
            </div>
          )}
        />

        {/* Tab Navigation */}
        <div className="flex gap-2 border-b pb-4">
          <Button
            variant={activeTab === 'settings' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('settings')}
            className={cn('gap-2 transition-all duration-300', activeTab === 'settings' && 'bg-gradient-to-r from-blue-600 to-violet-600 shadow-lg shadow-blue-500/25')}
          >
            <Settings className="w-4 h-4" />
            Ayarlar
          </Button>
          <Button
            variant={activeTab === 'widget' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('widget')}
            className={cn('gap-2 transition-all duration-300', activeTab === 'widget' && 'bg-gradient-to-r from-blue-600 to-violet-600 shadow-lg shadow-blue-500/25')}
          >
            <Globe className="w-4 h-4" />
            Web Widget
          </Button>
          <Button
            variant={activeTab === 'whatsapp' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('whatsapp')}
            className={cn('gap-2 transition-all duration-300', activeTab === 'whatsapp' && 'bg-gradient-to-r from-green-500 to-emerald-600 shadow-lg shadow-green-500/25')}
          >
            <Smartphone className="w-4 h-4" />
            WhatsApp
            {whatsappAccount?.is_active && (
              <Badge variant="success" className="ml-1 text-xs">Bağlı</Badge>
            )}
          </Button>
        </div>

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="glass-card animate-fade-in-up">
              <CardHeader>
                <CardTitle>Bot Ayarları</CardTitle>
                <CardDescription>Botunuzun davranışını ve görünümünü özelleştirin</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Bot Adı</Label>
                    <Input
                      id="name"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">Açıklama</Label>
                    <Textarea
                      id="description"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="Bot hakkında kısa bir açıklama"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="welcome_message">Karşılama Mesajı</Label>
                    <Textarea
                      id="welcome_message"
                      value={formData.welcome_message}
                      onChange={(e) => setFormData({ ...formData, welcome_message: e.target.value })}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="primary_color">Ana Renk</Label>
                      <div className="flex gap-2">
                        <input
                          type="color"
                          id="primary_color"
                          value={formData.primary_color}
                          onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
                          className="w-12 h-10 rounded-lg border cursor-pointer"
                        />
                        <Input
                          value={formData.primary_color}
                          onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
                          className="flex-1"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Widget Pozisyonu</Label>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant={formData.widget_position === 'left' ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => setFormData({ ...formData, widget_position: 'left' })}
                        >
                          Sol
                        </Button>
                        <Button
                          type="button"
                          variant={formData.widget_position === 'right' ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => setFormData({ ...formData, widget_position: 'right' })}
                        >
                          Sağ
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    <input
                      type="checkbox"
                      id="is_active"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      className="rounded"
                    />
                    <Label htmlFor="is_active">Bot aktif</Label>
                  </div>

                  <Button
                    type="submit"
                    className="w-full bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 btn-shimmer shadow-lg shadow-blue-500/25"
                    disabled={updateMutation.isPending}
                  >
                    <Save className="w-4 h-4 mr-2" />
                    {updateMutation.isPending ? 'Kaydediliyor...' : 'Kaydet'}
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="glass-card animate-fade-in-up" style={{ animationDelay: '100ms' }}>
              <CardHeader>
                <CardTitle>Widget Önizleme</CardTitle>
                <CardDescription>Botunuzun web sitenizde nasıl görüneceği</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="relative h-80 bg-slate-100 dark:bg-slate-800 rounded-xl overflow-hidden">
                  <div
                    className={`absolute bottom-4 ${formData.widget_position === 'right' ? 'right-4' : 'left-4'}`}
                  >
                    <div
                      className="w-14 h-14 rounded-full flex items-center justify-center shadow-lg cursor-pointer hover:scale-110 transition-transform animate-breathe"
                      style={{ backgroundColor: formData.primary_color }}
                    >
                      <MessageSquare className="w-6 h-6 text-white" />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Widget Tab */}
        {activeTab === 'widget' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="w-5 h-5 text-blue-600" />
                  Web Widget Kurulumu
                </CardTitle>
                <CardDescription>Widget'ı web sitenize eklemek için bu adımları izleyin</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0">
                      <span className="text-blue-600 font-bold">1</span>
                    </div>
                    <div>
                      <h4 className="font-medium">Kodu kopyalayın</h4>
                      <p className="text-sm text-muted-foreground">Aşağıdaki kodu kopyalayın</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0">
                      <span className="text-blue-600 font-bold">2</span>
                    </div>
                    <div>
                      <h4 className="font-medium">Web sitenize ekleyin</h4>
                      <p className="text-sm text-muted-foreground">{`</body>`} etiketinden hemen önce yapıştırın</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center flex-shrink-0">
                      <Check className="w-4 h-4 text-green-600" />
                    </div>
                    <div>
                      <h4 className="font-medium">Hazır!</h4>
                      <p className="text-sm text-muted-foreground">Widget otomatik olarak görünecek</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Widget Kodu</CardTitle>
                <CardDescription>Bu kodu web sitenize ekleyin</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-sm overflow-x-auto glass-card border border-slate-700">
                  <code>
                    {`<script src="${widgetBaseUrl}/widget.js" data-bot-key="${bot?.public_key}" data-api-url="${widgetBaseUrl}"></script>`}
                  </code>
                </div>
                <Button className="w-full" variant="outline" onClick={copyWidgetCode}>
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 mr-2 text-green-600" />
                      Kopyalandı
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4 mr-2" />
                      Kodu Kopyala
                    </>
                  )}
                </Button>

                <div className="p-4 rounded-xl border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    <strong>Bot Key:</strong> <code className="bg-yellow-100 dark:bg-yellow-900/50 px-1 rounded">{bot?.public_key}</code>
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* WhatsApp Tab */}
        {activeTab === 'whatsapp' && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Smartphone className="w-5 h-5 text-green-600" />
                  WhatsApp Bağlantısı
                </CardTitle>
                <CardDescription>Embedded Signup ile hızlı ve güvenli kurulum</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {whatsappAccount?.is_active ? (
                  <div className="space-y-4">
                    <div className="p-4 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-green-100 dark:bg-green-900/40 flex items-center justify-center">
                          <Check className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                          <h4 className="font-medium text-green-800 dark:text-green-200">WhatsApp Bağlı</h4>
                          <p className="text-sm text-green-600 dark:text-green-400">Kurulum tamamlandı ve aktif</p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Bağlı Numara</Label>
                      <Input value={whatsappAccount.display_phone_number || '-'} disabled />
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Webhook Durumu</Label>
                        <Input value={whatsappAccount.webhook_status} disabled />
                      </div>
                      <div className="space-y-2">
                        <Label>Token Durumu</Label>
                        <Input value={whatsappAccount.token_status} disabled />
                      </div>
                    </div>

                    <Link href="/dashboard/setup/whatsapp">
                      <Button variant="outline" className="w-full">
                        Kurulumu Yönet
                      </Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="w-6 h-6 text-slate-500 flex-shrink-0" />
                        <div>
                          <h4 className="font-medium">Henüz bağlı değil</h4>
                          <p className="text-sm text-muted-foreground">
                            WhatsApp hesabınızı tek tıkla bağlayın ve mesajları canlı alın.
                          </p>
                        </div>
                      </div>
                    </div>

                    <Link href="/dashboard/setup/whatsapp">
                      <Button className="w-full bg-green-600 hover:bg-green-700">
                        <Smartphone className="w-4 h-4 mr-2" />
                        WhatsApp'ı Bağla
                      </Button>
                    </Link>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Nasıl Çalışır?</CardTitle>
                <CardDescription>Embedded Signup ile otomatik bağlantı</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-4">
                  {[
                    { title: 'Meta ile giriş', desc: 'Facebook hesabınızla oturum açın' },
                    { title: 'WhatsApp hesabı seçin', desc: 'Mevcut WABA veya yeni hesap' },
                    { title: 'Telefon numarası doğrulayın', desc: 'Numara seçimi ve doğrulama' },
                    { title: 'Otomatik webhook', desc: 'Webhook kurulumu arka planda yapılır' },
                    { title: 'Bot hazır', desc: 'Mesajlar otomatik yönlendirilir' },
                  ].map((step, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0">
                        <span className="text-xs text-blue-600 font-bold">{i + 1}</span>
                      </div>
                      <div>
                        <h4 className="text-sm font-medium">{step.title}</h4>
                        <p className="text-xs text-muted-foreground">{step.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <a
                  href="/docs/WHATSAPP_EMBEDDED_SIGNUP.md"
                  target="_blank"
                  className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
                >
                  <ExternalLink className="w-4 h-4" />
                  Embedded Signup rehberi
                </a>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </ContentContainer>
  )
}
