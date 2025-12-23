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
  AlertCircle,
  CheckCircle2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { botApi, whatsappApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

export default function BotEditPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const botId = params.botId as string
  const [copied, setCopied] = useState(false)
  const [activeTab, setActiveTab] = useState<'settings' | 'widget' | 'whatsapp'>('settings')
  const [isWhatsAppDialogOpen, setIsWhatsAppDialogOpen] = useState(false)
  const [whatsappForm, setWhatsappForm] = useState({
    whatsapp_phone_number_id: '',
    whatsapp_business_account_id: '',
    access_token: '',
    webhook_verify_token: '',
  })

  const { data: bot, isLoading } = useQuery({
    queryKey: ['bot', botId],
    queryFn: () => botApi.get(botId).then(res => res.data),
  })

  const { data: whatsappIntegration } = useQuery({
    queryKey: ['whatsapp', botId],
    queryFn: () => whatsappApi.getIntegration(botId).then(res => res.data).catch(() => null),
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

  const whatsappMutation = useMutation({
    mutationFn: (data: typeof whatsappForm) => whatsappApi.createIntegration(botId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp', botId] })
      setIsWhatsAppDialogOpen(false)
      toast({
        title: 'WhatsApp Bağlandı',
        description: 'WhatsApp entegrasyonu başarıyla kuruldu.',
      })
    },
    onError: () => {
      toast({
        title: 'Hata',
        description: 'WhatsApp entegrasyonu kurulamadı. Bilgileri kontrol edin.',
        variant: 'destructive',
      })
    },
  })

  const copyWidgetCode = async () => {
    const code = `<script src="${window.location.origin}/widget.js" data-bot-key="${bot?.public_key}"></script>`
    await navigator.clipboard.writeText(code)
    setCopied(true)
    toast({
      title: 'Kopyalandı',
      description: 'Widget kodu panoya kopyalandı.',
    })
    setTimeout(() => setCopied(false), 2000)
  }

  const copyWebhookUrl = async () => {
    const url = `${window.location.origin.replace(':3000', ':8000')}/whatsapp/webhook`
    await navigator.clipboard.writeText(url)
    toast({
      title: 'Kopyalandı',
      description: 'Webhook URL panoya kopyalandı.',
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate(formData)
  }

  const handleWhatsAppSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    whatsappMutation.mutate(whatsappForm)
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/bots">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold">{bot?.name}</h1>
            <p className="text-muted-foreground">Bot ayarlarını düzenleyin</p>
          </div>
        </div>
        <Link href={`/dashboard/bots/${botId}/knowledge`}>
          <Button variant="outline">
            <BookOpen className="w-4 h-4 mr-2" />
            AI'ı Eğit
          </Button>
        </Link>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b pb-4">
        <Button
          variant={activeTab === 'settings' ? 'default' : 'ghost'}
          onClick={() => setActiveTab('settings')}
          className="gap-2"
        >
          <Settings className="w-4 h-4" />
          Ayarlar
        </Button>
        <Button
          variant={activeTab === 'widget' ? 'default' : 'ghost'}
          onClick={() => setActiveTab('widget')}
          className="gap-2"
        >
          <Globe className="w-4 h-4" />
          Web Widget
        </Button>
        <Button
          variant={activeTab === 'whatsapp' ? 'default' : 'ghost'}
          onClick={() => setActiveTab('whatsapp')}
          className="gap-2"
        >
          <Smartphone className="w-4 h-4" />
          WhatsApp
          {whatsappIntegration && (
            <Badge variant="success" className="ml-1 text-xs">Bağlı</Badge>
          )}
        </Button>
      </div>

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
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
                  className="w-full bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700" 
                  disabled={updateMutation.isPending}
                >
                  <Save className="w-4 h-4 mr-2" />
                  {updateMutation.isPending ? 'Kaydediliyor...' : 'Kaydet'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
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
                    className="w-14 h-14 rounded-full flex items-center justify-center shadow-lg cursor-pointer hover:scale-110 transition-transform"
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
                    <CheckCircle2 className="w-4 h-4 text-green-600" />
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
              <div className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-sm overflow-x-auto">
                <code>
                  {`<script src="${typeof window !== 'undefined' ? window.location.origin : ''}/widget.js" data-bot-key="${bot?.public_key}"></script>`}
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
                WhatsApp Entegrasyonu
              </CardTitle>
              <CardDescription>WhatsApp Business API ile bağlantı kurun</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {whatsappIntegration ? (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                    <div className="flex items-center gap-3">
                      <CheckCircle2 className="w-6 h-6 text-green-600" />
                      <div>
                        <h4 className="font-medium text-green-800 dark:text-green-200">WhatsApp Bağlı</h4>
                        <p className="text-sm text-green-600 dark:text-green-400">Entegrasyon aktif ve çalışıyor</p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Phone Number ID</Label>
                    <Input value={whatsappIntegration.whatsapp_phone_number_id} disabled />
                  </div>

                  <div className="space-y-2">
                    <Label>Business Account ID</Label>
                    <Input value={whatsappIntegration.whatsapp_business_account_id} disabled />
                  </div>

                  <Button 
                    variant="outline" 
                    className="w-full"
                    onClick={() => setIsWhatsAppDialogOpen(true)}
                  >
                    Ayarları Güncelle
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="w-6 h-6 text-slate-500 flex-shrink-0" />
                      <div>
                        <h4 className="font-medium">Henüz bağlı değil</h4>
                        <p className="text-sm text-muted-foreground">
                          WhatsApp Business API bilgilerinizi girerek bağlantı kurun.
                        </p>
                      </div>
                    </div>
                  </div>

                  <Button 
                    className="w-full bg-green-600 hover:bg-green-700"
                    onClick={() => setIsWhatsAppDialogOpen(true)}
                  >
                    <Smartphone className="w-4 h-4 mr-2" />
                    WhatsApp'ı Bağla
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Kurulum Adımları</CardTitle>
              <CardDescription>WhatsApp entegrasyonu için gerekli adımlar</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-4">
                {[
                  { title: 'Meta Business Suite', desc: 'İşletmenizi doğrulayın' },
                  { title: 'WhatsApp Business API', desc: 'Erişim izni alın' },
                  { title: 'Telefon Numarası', desc: 'Numara ekleyin ve doğrulayın' },
                  { title: 'API Bilgileri', desc: 'Token ve ID\'leri alın' },
                  { title: 'Webhook Ayarı', desc: 'Meta\'da webhook URL\'ini girin' },
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

              <div className="pt-4 border-t">
                <p className="text-sm text-muted-foreground mb-3">Webhook URL (Meta'ya girin):</p>
                <div className="flex gap-2">
                  <Input 
                    value={`${typeof window !== 'undefined' ? window.location.origin.replace(':3000', ':8000') : ''}/whatsapp/webhook`}
                    readOnly
                    className="text-xs font-mono"
                  />
                  <Button variant="outline" size="icon" onClick={copyWebhookUrl}>
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              <a 
                href="/docs/WHATSAPP_KURULUM.md" 
                target="_blank"
                className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
              >
                <ExternalLink className="w-4 h-4" />
                Detaylı kurulum rehberi
              </a>
            </CardContent>
          </Card>
        </div>
      )}

      {/* WhatsApp Setup Dialog */}
      <Dialog open={isWhatsAppDialogOpen} onOpenChange={setIsWhatsAppDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <div className="w-12 h-12 rounded-2xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
              <Smartphone className="w-6 h-6 text-green-600" />
            </div>
            <DialogTitle className="text-2xl">WhatsApp Bağlantısı</DialogTitle>
            <DialogDescription>
              Meta Business Suite'den aldığınız bilgileri girin
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleWhatsAppSubmit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="phone_id">Phone Number ID *</Label>
                <Input
                  id="phone_id"
                  placeholder="123456789012345"
                  value={whatsappForm.whatsapp_phone_number_id}
                  onChange={(e) => setWhatsappForm({ ...whatsappForm, whatsapp_phone_number_id: e.target.value })}
                  required
                />
                <p className="text-xs text-muted-foreground">Meta Developer Console → WhatsApp → API Setup</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="waba_id">WhatsApp Business Account ID *</Label>
                <Input
                  id="waba_id"
                  placeholder="987654321098765"
                  value={whatsappForm.whatsapp_business_account_id}
                  onChange={(e) => setWhatsappForm({ ...whatsappForm, whatsapp_business_account_id: e.target.value })}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="access_token">Access Token *</Label>
                <Textarea
                  id="access_token"
                  placeholder="EAAxxxxxxx..."
                  value={whatsappForm.access_token}
                  onChange={(e) => setWhatsappForm({ ...whatsappForm, access_token: e.target.value })}
                  required
                  rows={2}
                />
                <p className="text-xs text-muted-foreground">Kalıcı token için sistem kullanıcısı oluşturun</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="verify_token">Webhook Verify Token *</Label>
                <Input
                  id="verify_token"
                  placeholder="my_secret_token_123"
                  value={whatsappForm.webhook_verify_token}
                  onChange={(e) => setWhatsappForm({ ...whatsappForm, webhook_verify_token: e.target.value })}
                  required
                />
                <p className="text-xs text-muted-foreground">Kendiniz belirleyin, Meta'da aynısını girin</p>
              </div>
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setIsWhatsAppDialogOpen(false)}>
                İptal
              </Button>
              <Button 
                type="submit" 
                className="bg-green-600 hover:bg-green-700"
                disabled={whatsappMutation.isPending}
              >
                {whatsappMutation.isPending ? 'Bağlanıyor...' : 'Bağla'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
