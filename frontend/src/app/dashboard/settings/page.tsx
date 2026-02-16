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
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useAuthStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import { apiKeysApi, authApi, automationApi, subscriptionApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import Link from 'next/link'

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
  const [isCreateKeyOpen, setIsCreateKeyOpen] = useState(false)
  const [createdSecret, setCreatedSecret] = useState<string | null>(null)
  const [createKeyForm, setCreateKeyForm] = useState({ name: 'Default', current_password: '' })
  const [revokeKeyId, setRevokeKeyId] = useState<string | null>(null)
  const [revokePassword, setRevokePassword] = useState('')
  const [twoFactorSetupOpen, setTwoFactorSetupOpen] = useState(false)
  const [twoFactorDisableOpen, setTwoFactorDisableOpen] = useState(false)
  const [twoFactorSetupPassword, setTwoFactorSetupPassword] = useState('')
  const [twoFactorSetupSecret, setTwoFactorSetupSecret] = useState('')
  const [twoFactorSetupOtpUri, setTwoFactorSetupOtpUri] = useState('')
  const [twoFactorEnableCode, setTwoFactorEnableCode] = useState('')
  const [twoFactorDisablePassword, setTwoFactorDisablePassword] = useState('')
  const [twoFactorDisableCode, setTwoFactorDisableCode] = useState('')

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

  const { data: usageStats, isLoading: usageLoading } = useQuery({
    queryKey: ['usage-stats'],
    queryFn: () => subscriptionApi.getUsageStats().then(res => res.data),
    enabled: activeTab === 'api',
  })

  const apiAccessEnabled = usageStats?.features?.api_access === true

  const { data: apiKeys, isLoading: apiKeysLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => apiKeysApi.list({ include_revoked: true }).then(res => res.data),
    enabled: activeTab === 'api' && apiAccessEnabled,
  })

  const { data: twoFactorStatus } = useQuery({
    queryKey: ['two-factor-status'],
    queryFn: () => authApi.getTwoFactorStatus().then(res => res.data),
    enabled: activeTab === 'security',
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

  const createKeyMutation = useMutation({
    mutationFn: (payload: { name: string; current_password: string }) => apiKeysApi.create(payload),
    onSuccess: (response) => {
      const secret = response.data?.secret
      setCreatedSecret(secret || null)
      setCreateKeyForm({ name: 'Default', current_password: '' })
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      toast({ title: 'API anahtarı oluşturuldu', description: 'Anahtar sadece bir kez gösterilecektir.' })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'API anahtarı oluşturulamadı',
        variant: 'destructive',
      })
    },
  })

  const revokeKeyMutation = useMutation({
    mutationFn: ({ id, current_password }: { id: string; current_password: string }) =>
      apiKeysApi.revoke(id, { current_password }),
    onSuccess: () => {
      setRevokeKeyId(null)
      setRevokePassword('')
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      toast({ title: 'API anahtarı iptal edildi' })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'API anahtarı iptal edilemedi',
        variant: 'destructive',
      })
    },
  })

  const changePasswordMutation = useMutation({
    mutationFn: (payload: { current_password: string; new_password: string }) => authApi.changePassword(payload),
    onSuccess: () => {
      toast({
        title: 'Şifre güncellendi',
        description: 'Güvenlik için tekrar giriş yapmanız önerilir.',
      })
      setSecurityData({ current_password: '', new_password: '', confirm_password: '' })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Şifre güncellenemedi',
        variant: 'destructive',
      })
    },
  })

  const setupTwoFactorMutation = useMutation({
    mutationFn: (payload: { current_password: string }) => authApi.setupTwoFactor(payload),
    onSuccess: (response) => {
      setTwoFactorSetupSecret(response.data?.secret || '')
      setTwoFactorSetupOtpUri(response.data?.otpauth_uri || '')
      toast({
        title: '2FA kurulumu hazır',
        description: 'Authenticator uygulamasına anahtarı ekleyip kodu doğrulayın.',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || '2FA kurulumu başlatılamadı',
        variant: 'destructive',
      })
    },
  })

  const enableTwoFactorMutation = useMutation({
    mutationFn: (payload: { code: string }) => authApi.enableTwoFactor(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['two-factor-status'] })
      setTwoFactorSetupOpen(false)
      setTwoFactorSetupPassword('')
      setTwoFactorSetupSecret('')
      setTwoFactorSetupOtpUri('')
      setTwoFactorEnableCode('')
      toast({ title: '2FA aktif edildi' })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || '2FA aktif edilemedi',
        variant: 'destructive',
      })
    },
  })

  const disableTwoFactorMutation = useMutation({
    mutationFn: (payload: { current_password: string; code: string }) => authApi.disableTwoFactor(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['two-factor-status'] })
      setTwoFactorDisableOpen(false)
      setTwoFactorDisablePassword('')
      setTwoFactorDisableCode('')
      toast({ title: '2FA kapatıldı' })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || '2FA kapatılamadı',
        variant: 'destructive',
      })
    },
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

  const handlePasswordChange = async () => {
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

    if (securityData.new_password.length < 8) {
      toast({
        title: 'Hata',
        description: 'Yeni şifre en az 8 karakter olmalıdır.',
        variant: 'destructive',
      })
      return
    }

    await changePasswordMutation.mutateAsync({
      current_password: securityData.current_password,
      new_password: securityData.new_password,
    })
  }

  const copyValue = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value)
      toast({ title: 'Kopyalandı', description: label })
    } catch {
      toast({ title: 'Hata', description: 'Kopyalama başarısız', variant: 'destructive' })
    }
  }

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Ayarlar"
          description="Hesap ve işletme ayarlarınızı yönetin."
          icon={<Icon3DBadge icon={Settings} from="from-slate-600" to="to-zinc-500" />}
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
                      'group w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                      activeTab === tab.id
                        ? 'nav-active-glow text-primary'
                        : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                    )}
                  >
                    <Icon3DBadge
                      icon={tab.icon}
                      size="sm"
                      active
                      from={activeTab === tab.id ? 'from-primary' : 'from-slate-200 dark:from-slate-800'}
                      to={activeTab === tab.id ? 'to-violet-500' : 'to-slate-50 dark:to-slate-700'}
                      className={cn(
                        'transition-transform duration-200 group-hover:-translate-y-0.5',
                        activeTab === tab.id && 'ring-2 ring-primary/25'
                      )}
                    />
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
                        <p className="text-sm text-muted-foreground">Profil avatarı ad soyad baş harfinden otomatik üretilir.</p>
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
                      <p className="text-sm text-muted-foreground">Marka rozeti işletme adının baş harfinden otomatik oluşturulur.</p>
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
                        disabled={changePasswordMutation.isPending}
                      >
                        {changePasswordMutation.isPending ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Güncelleniyor...
                          </>
                        ) : (
                          'Şifreyi Güncelle'
                        )}
                      </Button>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <p className="font-medium">İki Faktörlü Doğrulama</p>
                        <p className="text-sm text-muted-foreground">
                          Authenticator uygulamasıyla giriş güvenliğini artırın
                        </p>
                      </div>
                      {twoFactorStatus?.enabled ? (
                        <Badge variant="success">Aktif</Badge>
                      ) : (
                        <Badge variant="outline">Pasif</Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {!twoFactorStatus?.enabled ? (
                        <Button
                          variant="outline"
                          onClick={() => {
                            setTwoFactorSetupOpen(true)
                            setTwoFactorSetupPassword('')
                            setTwoFactorSetupSecret('')
                            setTwoFactorSetupOtpUri('')
                            setTwoFactorEnableCode('')
                          }}
                        >
                          2FA Kurulumu Başlat
                        </Button>
                      ) : (
                        <Button
                          variant="destructive"
                          onClick={() => {
                            setTwoFactorDisableOpen(true)
                            setTwoFactorDisablePassword('')
                            setTwoFactorDisableCode('')
                          }}
                        >
                          2FA Kapat
                        </Button>
                      )}
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
                  {!apiAccessEnabled && !usageLoading && usageStats && (
                    <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
                        <div>
                          <p className="font-medium text-amber-900 dark:text-amber-100">API erişimi kapalı</p>
                          <p className="text-sm text-amber-800 dark:text-amber-200">API anahtarları için planınızı yükseltin (API Access).</p>
                        </div>
                      </div>
                      <Link href="/dashboard/billing">
                        <Button className="bg-gradient-to-r from-amber-600 to-orange-600">Planları Gör</Button>
                      </Link>
                    </div>
                  )}

                  {apiAccessEnabled && (
                    <div className="space-y-3">
                      {apiKeysLoading ? (
                        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 text-sm text-muted-foreground">
                          Yükleniyor...
                        </div>
                      ) : (
                        (apiKeys?.items || []).map((key: any) => (
                          <div key={key.id} className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{key.name}</span>
                                {key.revoked_at ? (
                                  <Badge variant="outline">İptal</Badge>
                                ) : (
                                  <Badge variant="success">Aktif</Badge>
                                )}
                              </div>
                              <code className="text-sm text-muted-foreground">•••• •••• •••• {key.last4}</code>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <Button
                                variant="destructive"
                                size="sm"
                                disabled={Boolean(key.revoked_at)}
                                onClick={() => {
                                  setRevokeKeyId(key.id)
                                  setRevokePassword('')
                                }}
                              >
                                İptal Et
                              </Button>
                            </div>
                          </div>
                        ))
                      )}
                      {!apiKeysLoading && (apiKeys?.items || []).length === 0 && (
                        <div className="p-4 rounded-xl border border-dashed text-sm text-muted-foreground">
                          Henüz API anahtarı yok.
                        </div>
                      )}
                    </div>
                  )}

                  <div className="p-4 rounded-xl border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20">
                    <p className="text-sm text-yellow-800 dark:text-yellow-200">
                      <strong>Önemli:</strong> API anahtarınızı asla paylaşmayın.
                      Tehlikeye girdiğini düşünüyorsanız yeni bir anahtar oluşturun.
                    </p>
                  </div>

                  <Button
                    variant="outline"
                    disabled={!apiAccessEnabled}
                    onClick={() => {
                      setIsCreateKeyOpen(true)
                      setCreatedSecret(null)
                      setCreateKeyForm({ name: 'Default', current_password: '' })
                    }}
                  >
                    Yeni Anahtar Oluştur
                  </Button>
                </CardContent>
              </Card>
            )}

            <Dialog open={isCreateKeyOpen} onOpenChange={(open) => {
              setIsCreateKeyOpen(open)
              if (!open) {
                setCreatedSecret(null)
                setCreateKeyForm({ name: 'Default', current_password: '' })
              }
            }}>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>Yeni API Anahtarı</DialogTitle>
                  <DialogDescription>Güvenlik için oluşturma işleminde şifrenizi doğruluyoruz.</DialogDescription>
                </DialogHeader>

                {createdSecret ? (
                  <div className="space-y-3">
                    <div className="rounded-xl border p-4">
                      <p className="text-sm font-medium mb-2">Bu anahtar sadece bir kez gösterilir</p>
                      <code className="block break-all text-sm text-muted-foreground">{createdSecret}</code>
                    </div>
                    <Button onClick={() => copyValue(createdSecret, 'API anahtarı kopyalandı')}>
                      <Copy className="w-4 h-4 mr-2" />
                      Kopyala
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>Anahtar adı</Label>
                      <Input value={createKeyForm.name} onChange={(e) => setCreateKeyForm({ ...createKeyForm, name: e.target.value })} />
                    </div>
                    <div className="space-y-2">
                      <Label>Şifreniz</Label>
                      <Input type="password" value={createKeyForm.current_password} onChange={(e) => setCreateKeyForm({ ...createKeyForm, current_password: e.target.value })} />
                    </div>
                  </div>
                )}

                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsCreateKeyOpen(false)}>Kapat</Button>
                  {!createdSecret && (
                    <Button
                      onClick={() => createKeyMutation.mutate({ name: createKeyForm.name, current_password: createKeyForm.current_password })}
                      disabled={createKeyMutation.isPending || !createKeyForm.name.trim() || !createKeyForm.current_password}
                    >
                      {createKeyMutation.isPending ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Oluşturuluyor...
                        </>
                      ) : (
                        'Oluştur'
                      )}
                    </Button>
                  )}
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog open={Boolean(revokeKeyId)} onOpenChange={(open) => {
              if (!open) {
                setRevokeKeyId(null)
                setRevokePassword('')
              }
            }}>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>API Anahtarını İptal Et</DialogTitle>
                  <DialogDescription>İşlemi onaylamak için şifrenizi girin.</DialogDescription>
                </DialogHeader>
                <div className="space-y-2">
                  <Label>Şifreniz</Label>
                  <Input type="password" value={revokePassword} onChange={(e) => setRevokePassword(e.target.value)} />
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setRevokeKeyId(null)}>Vazgeç</Button>
                  <Button
                    variant="destructive"
                    onClick={() => revokeKeyId && revokeKeyMutation.mutate({ id: revokeKeyId, current_password: revokePassword })}
                    disabled={revokeKeyMutation.isPending || !revokeKeyId || !revokePassword}
                  >
                    {revokeKeyMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        İptal Ediliyor...
                      </>
                    ) : (
                      'İptal Et'
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog open={twoFactorSetupOpen} onOpenChange={(open) => {
              setTwoFactorSetupOpen(open)
              if (!open) {
                setTwoFactorSetupPassword('')
                setTwoFactorSetupSecret('')
                setTwoFactorSetupOtpUri('')
                setTwoFactorEnableCode('')
              }
            }}>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>2FA Kurulumu</DialogTitle>
                  <DialogDescription>
                    Önce şifrenizi doğrulayın, ardından authenticator kodunu onaylayın.
                  </DialogDescription>
                </DialogHeader>

                {!twoFactorSetupSecret ? (
                  <div className="space-y-2">
                    <Label>Şifreniz</Label>
                    <Input
                      type="password"
                      value={twoFactorSetupPassword}
                      onChange={(e) => setTwoFactorSetupPassword(e.target.value)}
                    />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="rounded-xl border p-4 space-y-2">
                      <p className="text-sm font-medium">Manuel anahtar</p>
                      <code className="block break-all text-sm text-muted-foreground">{twoFactorSetupSecret}</code>
                    </div>
                    <div className="rounded-xl border p-4 space-y-2">
                      <p className="text-sm font-medium">OTP URI</p>
                      <code className="block break-all text-xs text-muted-foreground">{twoFactorSetupOtpUri}</code>
                      <Button variant="outline" size="sm" onClick={() => copyValue(twoFactorSetupOtpUri, 'OTP URI kopyalandı')}>
                        <Copy className="w-4 h-4 mr-2" />
                        URI Kopyala
                      </Button>
                    </div>
                    <div className="space-y-2">
                      <Label>Authenticator Kodu</Label>
                      <Input
                        placeholder="6 haneli kod"
                        value={twoFactorEnableCode}
                        onChange={(e) => setTwoFactorEnableCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                        className="text-center tracking-[0.3em]"
                        maxLength={6}
                      />
                    </div>
                  </div>
                )}

                <DialogFooter>
                  <Button variant="outline" onClick={() => setTwoFactorSetupOpen(false)}>Kapat</Button>
                  {!twoFactorSetupSecret ? (
                    <Button
                      onClick={() => setupTwoFactorMutation.mutate({ current_password: twoFactorSetupPassword })}
                      disabled={setupTwoFactorMutation.isPending || !twoFactorSetupPassword}
                    >
                      {setupTwoFactorMutation.isPending ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Hazırlanıyor...
                        </>
                      ) : (
                        'Kurulumu Başlat'
                      )}
                    </Button>
                  ) : (
                    <Button
                      onClick={() => enableTwoFactorMutation.mutate({ code: twoFactorEnableCode })}
                      disabled={enableTwoFactorMutation.isPending || twoFactorEnableCode.length !== 6}
                    >
                      {enableTwoFactorMutation.isPending ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Doğrulanıyor...
                        </>
                      ) : (
                        '2FA Aktif Et'
                      )}
                    </Button>
                  )}
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog open={twoFactorDisableOpen} onOpenChange={(open) => {
              setTwoFactorDisableOpen(open)
              if (!open) {
                setTwoFactorDisablePassword('')
                setTwoFactorDisableCode('')
              }
            }}>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>2FA Kapat</DialogTitle>
                  <DialogDescription>
                    Güvenlik için şifrenizi ve güncel authenticator kodunu girin.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label>Şifreniz</Label>
                    <Input
                      type="password"
                      value={twoFactorDisablePassword}
                      onChange={(e) => setTwoFactorDisablePassword(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Authenticator Kodu</Label>
                    <Input
                      value={twoFactorDisableCode}
                      onChange={(e) => setTwoFactorDisableCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                      className="text-center tracking-[0.3em]"
                      maxLength={6}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setTwoFactorDisableOpen(false)}>Vazgeç</Button>
                  <Button
                    variant="destructive"
                    onClick={() => disableTwoFactorMutation.mutate({ current_password: twoFactorDisablePassword, code: twoFactorDisableCode })}
                    disabled={disableTwoFactorMutation.isPending || !twoFactorDisablePassword || twoFactorDisableCode.length !== 6}
                  >
                    {disableTwoFactorMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Kapatılıyor...
                      </>
                    ) : (
                      '2FA Kapat'
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

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
