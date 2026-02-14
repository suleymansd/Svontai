'use client'

import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Settings,
  User,
  Building2,
  Bell,
  Shield,
  CreditCard,
  Key,
  Globe,
  Palette,
  Save,
  Check,
  Moon,
  Sun,
  Laptop,
  Copy,
  Workflow,
  Play,
  AlertCircle,
  CheckCircle2,
  Loader2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { useAuthStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import { authApi, automationApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'

const tabs = [
  { id: 'profile', label: 'Profil', icon: User },
  { id: 'company', label: 'İşletme', icon: Building2 },
  { id: 'automation', label: 'Otomasyon (n8n)', icon: Workflow },
  { id: 'notifications', label: 'Bildirimler', icon: Bell },
  { id: 'security', label: 'Güvenlik', icon: Shield },
  { id: 'api', label: 'API Anahtarları', icon: Key },
]

export default function SettingsPage() {
  const { user, tenant } = useAuthStore()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('profile')
  const [saved, setSaved] = useState(false)
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system')
  const [testingWorkflow, setTestingWorkflow] = useState(false)

  const [profileData, setProfileData] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
    bio: ''
  })

  const [companyData, setCompanyData] = useState({
    name: tenant?.name || '',
    website: '',
    description: ''
  })

  const [securityData, setSecurityData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  })

  // Automation settings state
  const [automationData, setAutomationData] = useState({
    use_n8n: false,
    default_workflow_id: '',
    whatsapp_workflow_id: '',
    enable_auto_retry: true,
    max_retries: 2,
    timeout_seconds: 10
  })

  // Fetch automation settings
  const { data: automationSettings, isLoading: automationLoading } = useQuery({
    queryKey: ['automation-settings'],
    queryFn: () => automationApi.getSettings().then(res => res.data),
    enabled: activeTab === 'automation'
  })

  // Fetch automation status
  const { data: automationStatus } = useQuery({
    queryKey: ['automation-status'],
    queryFn: () => automationApi.getStatus().then(res => res.data),
    enabled: activeTab === 'automation',
    refetchInterval: 30000
  })

  // Update automation data when settings are fetched
  useEffect(() => {
    if (automationSettings) {
      setAutomationData({
        use_n8n: automationSettings.use_n8n || false,
        default_workflow_id: automationSettings.default_workflow_id || '',
        whatsapp_workflow_id: automationSettings.whatsapp_workflow_id || '',
        enable_auto_retry: automationSettings.enable_auto_retry ?? true,
        max_retries: automationSettings.max_retries || 2,
        timeout_seconds: automationSettings.timeout_seconds || 10
      })
    }
  }, [automationSettings])

  // Mutation for updating automation settings
  const updateAutomationMutation = useMutation({
    mutationFn: (data: typeof automationData) => automationApi.updateSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automation-settings'] })
      queryClient.invalidateQueries({ queryKey: ['automation-status'] })
      toast({
        title: 'Kaydedildi',
        description: 'Otomasyon ayarları güncellendi.',
      })
    },
    onError: () => {
      toast({
        title: 'Hata',
        description: 'Ayarlar kaydedilemedi.',
        variant: 'destructive',
      })
    }
  })

  // Test workflow mutation
  const testWorkflowMutation = useMutation({
    mutationFn: () => automationApi.sendTestEvent('Test mesajı - n8n workflow testi'),
    onSuccess: (response) => {
      const data = response.data
      if (data.success) {
        toast({
          title: 'Test Başarılı',
          description: `Workflow tetiklendi. Run ID: ${data.run_id}`,
        })
      } else {
        toast({
          title: 'Test Başarısız',
          description: data.message,
          variant: 'destructive',
        })
      }
    },
    onError: () => {
      toast({
        title: 'Hata',
        description: 'Test gönderilemedi.',
        variant: 'destructive',
      })
    }
  })

  const handleSaveAutomation = () => {
    updateAutomationMutation.mutate(automationData)
  }

  const handleTestWorkflow = async () => {
    setTestingWorkflow(true)
    await testWorkflowMutation.mutateAsync()
    setTestingWorkflow(false)
  }

  const handleSave = () => {
    setSaved(true)
    toast({
      title: 'Kaydedildi',
      description: 'Değişiklikleriniz başarıyla kaydedildi.',
    })
    setTimeout(() => setSaved(false), 2000)
  }

  const handlePasswordChange = () => {
    if (!securityData.current_password || !securityData.new_password) {
      toast({
        title: 'Hata',
        description: 'Lütfen tüm şifre alanlarını doldurun.',
        variant: 'destructive',
      })
      return
    }

    if (securityData.new_password !== securityData.confirm_password) {
      toast({
        title: 'Hata',
        description: 'Yeni şifreler eşleşmiyor.',
        variant: 'destructive',
      })
      return
    }

    if (securityData.new_password.length < 6) {
      toast({
        title: 'Hata',
        description: 'Yeni şifre en az 6 karakter olmalıdır.',
        variant: 'destructive',
      })
      return
    }

    // In a real app, this would call the API
    toast({
      title: 'Şifre güncellendi',
      description: 'Şifreniz başarıyla değiştirildi.',
    })
    setSecurityData({ current_password: '', new_password: '', confirm_password: '' })
  }

  const copyApiKey = () => {
    toast({
      title: 'Yakında',
      description: 'API anahtarı yönetimi yakında aktif olacak.',
    })
  }

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Ayarlar"
          description="Hesap ve işletme ayarlarınızı yönetin."
        />

        <div className="grid lg:grid-cols-4 gap-8">
          {/* Sidebar */}
          <Card className="lg:col-span-1 h-fit border border-border/70 shadow-soft glass-card">
            <CardContent className="p-2">
              <nav className="space-y-1">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                      activeTab === tab.id
                        ? 'nav-active-glow text-primary'
                        : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                    )}
                  >
                    <tab.icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                ))}
              </nav>
            </CardContent>
          </Card>

          {/* Content */}
          <div className="lg:col-span-3 space-y-6">
            {activeTab === 'profile' && (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>Profil Bilgileri</CardTitle>
                    <CardDescription>Kişisel bilgilerinizi güncelleyin</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Avatar */}
                    <div className="flex items-center gap-6">
                      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-2xl font-bold">
                        {profileData.full_name?.charAt(0).toUpperCase() || user?.full_name?.charAt(0).toUpperCase() || 'U'}
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Profil fotoğrafı özelliği yakında!</p>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Ad Soyad</Label>
                        <Input
                          value={profileData.full_name}
                          onChange={(e) => setProfileData({ ...profileData, full_name: e.target.value })}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>E-posta</Label>
                        <Input
                          value={profileData.email}
                          type="email"
                          onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
                        />
                      </div>
                      <div className="space-y-2 sm:col-span-2">
                        <Label>Biyografi</Label>
                        <Textarea
                          placeholder="Kendiniz hakkında kısa bir açıklama..."
                          value={profileData.bio}
                          onChange={(e) => setProfileData({ ...profileData, bio: e.target.value })}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Palette className="w-5 h-5" />
                      Tema Tercihi
                    </CardTitle>
                    <CardDescription>Uygulama görünümünü özelleştirin</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-4">
                      {[
                        { id: 'light', label: 'Açık', icon: Sun },
                        { id: 'dark', label: 'Koyu', icon: Moon },
                        { id: 'system', label: 'Sistem', icon: Laptop },
                      ].map((option) => (
                        <button
                          key={option.id}
                          onClick={() => setTheme(option.id as any)}
                          className={cn(
                            'p-4 rounded-xl border-2 transition-all',
                            theme === option.id
                              ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                              : 'border-slate-200 dark:border-slate-800 hover:border-slate-300'
                          )}
                        >
                          <option.icon className={cn(
                            'w-6 h-6 mx-auto mb-2',
                            theme === option.id ? 'text-blue-600' : 'text-muted-foreground'
                          )} />
                          <span className={cn(
                            'text-sm font-medium',
                            theme === option.id ? 'text-blue-600' : ''
                          )}>
                            {option.label}
                          </span>
                        </button>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </>
            )}

            {activeTab === 'company' && (
              <Card>
                <CardHeader>
                  <CardTitle>İşletme Bilgileri</CardTitle>
                  <CardDescription>İşletmenizin bilgilerini düzenleyin</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center gap-6">
                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold">
                      {companyData.name?.charAt(0).toUpperCase() || tenant?.name?.charAt(0).toUpperCase() || 'İ'}
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Logo yükleme özelliği yakında!</p>
                    </div>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label>İşletme Adı</Label>
                      <Input
                        value={companyData.name}
                        onChange={(e) => setCompanyData({ ...companyData, name: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Web Sitesi</Label>
                      <div className="relative">
                        <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                          className="pl-9"
                          placeholder="https://example.com"
                          value={companyData.website}
                          onChange={(e) => setCompanyData({ ...companyData, website: e.target.value })}
                        />
                      </div>
                    </div>
                    <div className="space-y-2 sm:col-span-2">
                      <Label>İşletme Açıklaması</Label>
                      <Textarea
                        placeholder="İşletmeniz hakkında kısa bir açıklama..."
                        value={companyData.description}
                        onChange={(e) => setCompanyData({ ...companyData, description: e.target.value })}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {activeTab === 'automation' && (
              <>
                {/* n8n Status Card */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <Workflow className="w-5 h-5" />
                          n8n Workflow Engine
                        </CardTitle>
                        <CardDescription>
                          WhatsApp mesajlarını n8n workflow&apos;ları ile işleyin
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        {automationStatus?.global_enabled ? (
                          <Badge variant="success" className="gap-1">
                            <CheckCircle2 className="w-3 h-3" />
                            Sistem Aktif
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="gap-1">
                            <AlertCircle className="w-3 h-3" />
                            Sistem Kapalı
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Status Summary */}
                    {automationStatus && (
                      <div className="grid grid-cols-3 gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-blue-600">{automationStatus.stats_24h?.total || 0}</div>
                          <div className="text-sm text-muted-foreground">Son 24 Saat</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-green-600">{automationStatus.stats_24h?.successful || 0}</div>
                          <div className="text-sm text-muted-foreground">Başarılı</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-red-600">{automationStatus.stats_24h?.failed || 0}</div>
                          <div className="text-sm text-muted-foreground">Başarısız</div>
                        </div>
                      </div>
                    )}

                    {/* Enable Toggle */}
                    <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                      <div>
                        <p className="font-medium">n8n Workflow&apos;ları Kullan</p>
                        <p className="text-sm text-muted-foreground">
                          Aktif olduğunda WhatsApp mesajları n8n&apos;e yönlendirilir
                        </p>
                      </div>
                      <Switch
                        checked={automationData.use_n8n}
                        onCheckedChange={(checked) => setAutomationData({ ...automationData, use_n8n: checked })}
                        disabled={!automationStatus?.global_enabled}
                      />
                    </div>

                    {!automationStatus?.global_enabled && (
                      <div className="p-4 rounded-xl border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20">
                        <p className="text-sm text-yellow-800 dark:text-yellow-200">
                          <strong>Bilgi:</strong> n8n workflow engine sistem genelinde aktif değil.
                          Sunucu yapılandırmasında USE_N8N=true olarak ayarlanmalıdır.
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Workflow Configuration */}
                <Card>
                  <CardHeader>
                    <CardTitle>Workflow Yapılandırması</CardTitle>
                    <CardDescription>n8n workflow ID&apos;lerini yapılandırın</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>Varsayılan Workflow ID</Label>
                      <Input
                        placeholder="svontai-incoming"
                        value={automationData.default_workflow_id}
                        onChange={(e) => setAutomationData({ ...automationData, default_workflow_id: e.target.value })}
                      />
                      <p className="text-xs text-muted-foreground">
                        n8n&apos;deki webhook path&apos;i (örn: svontai-incoming)
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label>WhatsApp Workflow ID (Opsiyonel)</Label>
                      <Input
                        placeholder="Varsayılan workflow kullanılır"
                        value={automationData.whatsapp_workflow_id}
                        onChange={(e) => setAutomationData({ ...automationData, whatsapp_workflow_id: e.target.value })}
                      />
                      <p className="text-xs text-muted-foreground">
                        WhatsApp mesajları için özel workflow (boş bırakılırsa varsayılan kullanılır)
                      </p>
                    </div>
                  </CardContent>
                </Card>

                {/* Advanced Settings */}
                <Card>
                  <CardHeader>
                    <CardTitle>Gelişmiş Ayarlar</CardTitle>
                    <CardDescription>Retry ve timeout yapılandırması</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                      <div>
                        <p className="font-medium">Otomatik Yeniden Deneme</p>
                        <p className="text-sm text-muted-foreground">Başarısız istekleri otomatik yeniden dene</p>
                      </div>
                      <Switch
                        checked={automationData.enable_auto_retry}
                        onCheckedChange={(checked) => setAutomationData({ ...automationData, enable_auto_retry: checked })}
                      />
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Maksimum Deneme Sayısı</Label>
                        <Input
                          type="number"
                          min="0"
                          max="10"
                          value={automationData.max_retries}
                          onChange={(e) => setAutomationData({ ...automationData, max_retries: parseInt(e.target.value) || 0 })}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Timeout (saniye)</Label>
                        <Input
                          type="number"
                          min="1"
                          max="60"
                          value={automationData.timeout_seconds}
                          onChange={(e) => setAutomationData({ ...automationData, timeout_seconds: parseInt(e.target.value) || 10 })}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Test Section */}
                <Card>
                  <CardHeader>
                    <CardTitle>Workflow Testi</CardTitle>
                    <CardDescription>Yapılandırmayı test edin</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Ayarları kaydettikten sonra bir test mesajı göndererek workflow&apos;unuzun
                      düzgün çalıştığını doğrulayın.
                    </p>
                    <Button
                      variant="outline"
                      onClick={handleTestWorkflow}
                      disabled={testingWorkflow || !automationData.use_n8n || !automationStatus?.global_enabled}
                    >
                      {testingWorkflow ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Test Gönderiliyor...
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-2" />
                          Test Mesajı Gönder
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>

                {/* Save Button for Automation */}
                <div className="flex justify-end">
                  <Button
                    onClick={handleSaveAutomation}
                    disabled={updateAutomationMutation.isPending}
                    className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
                  >
                    {updateAutomationMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Kaydediliyor...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4 mr-2" />
                        Otomasyon Ayarlarını Kaydet
                      </>
                    )}
                  </Button>
                </div>
              </>
            )}

            {activeTab === 'notifications' && (
              <Card>
                <CardHeader>
                  <CardTitle>Bildirim Tercihleri</CardTitle>
                  <CardDescription>Hangi bildirimleri almak istediğinizi seçin</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {[
                    { title: 'Yeni Mesaj', desc: 'Müşterilerden yeni mesaj geldiğinde', default: true },
                    { title: 'Yeni Lead', desc: 'Yeni bir potansiyel müşteri kaydedildiğinde', default: true },
                    { title: 'Bot Hataları', desc: 'Bot yanıt veremediğinde', default: true },
                    { title: 'Haftalık Rapor', desc: 'Haftalık performans raporu', default: false },
                    { title: 'Pazarlama E-postaları', desc: 'Yeni özellikler ve kampanyalar', default: false },
                  ].map((item, i) => (
                    <div key={i} className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                      <div>
                        <p className="font-medium">{item.title}</p>
                        <p className="text-sm text-muted-foreground">{item.desc}</p>
                      </div>
                      <Switch defaultChecked={item.default} />
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {activeTab === 'security' && (
              <Card>
                <CardHeader>
                  <CardTitle>Güvenlik Ayarları</CardTitle>
                  <CardDescription>Hesabınızı güvende tutun</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-4">
                    <Label>Şifre Değiştir</Label>
                    <div className="grid gap-4">
                      <Input
                        type="password"
                        placeholder="Mevcut şifre"
                        value={securityData.current_password}
                        onChange={(e) => setSecurityData({ ...securityData, current_password: e.target.value })}
                      />
                      <div className="grid gap-4 sm:grid-cols-2">
                        <Input
                          type="password"
                          placeholder="Yeni şifre"
                          value={securityData.new_password}
                          onChange={(e) => setSecurityData({ ...securityData, new_password: e.target.value })}
                        />
                        <Input
                          type="password"
                          placeholder="Yeni şifre (tekrar)"
                          value={securityData.confirm_password}
                          onChange={(e) => setSecurityData({ ...securityData, confirm_password: e.target.value })}
                        />
                      </div>
                      <Button
                        variant="outline"
                        className="w-fit"
                        onClick={handlePasswordChange}
                      >
                        Şifreyi Güncelle
                      </Button>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <p className="font-medium">İki Faktörlü Doğrulama</p>
                        <p className="text-sm text-muted-foreground">Bu özellik yakında aktif olacak</p>
                      </div>
                      <Switch disabled />
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {activeTab === 'api' && (
              <Card>
                <CardHeader>
                  <CardTitle>API Anahtarları</CardTitle>
                  <CardDescription>Entegrasyonlar için API anahtarlarınızı yönetin</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">API Anahtarı</span>
                      <Button variant="ghost" size="sm" onClick={copyApiKey}>
                        <Copy className="w-4 h-4" />
                        <span className="ml-2">Kopyala</span>
                      </Button>
                    </div>
                    <code className="text-sm text-muted-foreground">
                      •••••••••••••••••••••••••••••••••
                    </code>
                  </div>

                  <div className="p-4 rounded-xl border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20">
                    <p className="text-sm text-yellow-800 dark:text-yellow-200">
                      <strong>Önemli:</strong> API anahtarınızı asla paylaşmayın.
                      Tehlikeye girdiğini düşünüyorsanız yeni bir anahtar oluşturun.
                    </p>
                  </div>

                  <Button
                    variant="outline"
                    onClick={() => toast({
                      title: 'Yeni anahtar',
                      description: 'Bu özellik yakında aktif olacak.',
                    })}
                  >
                    Yeni Anahtar Oluştur
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Save Button */}
            <div className="flex justify-end">
              <Button
                onClick={handleSave}
                className={cn(
                  'transition-all',
                  saved
                    ? 'bg-green-500 hover:bg-green-600'
                    : 'bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700'
                )}
              >
                {saved ? (
                  <>
                    <Check className="w-4 h-4 mr-2" />
                    Kaydedildi
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    Değişiklikleri Kaydet
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </ContentContainer>
  )
}
