'use client'

import { useState, useEffect } from 'react'
import { 
  Settings, 
  Database,
  Server,
  Cpu,
  Activity,
  RefreshCw,
  Check,
  X,
  AlertCircle
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { adminApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'

interface SystemHealth {
  status: string
  database: string
  api: string
  uptime: string
}

export default function SettingsPage() {
  const { toast } = useToast()
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchHealth = async () => {
    try {
      const response = await adminApi.getHealth()
      setHealth(response.data)
    } catch (error) {
      console.error('Failed to fetch health:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchHealth()
  }, [])

  const handleRefresh = () => {
    setRefreshing(true)
    fetchHealth()
  }

  const getStatusIcon = (status: string) => {
    if (status === 'healthy' || status === 'operational') {
      return <Check className="w-5 h-5 text-green-500" />
    } else if (status === 'unhealthy') {
      return <X className="w-5 h-5 text-red-500" />
    }
    return <AlertCircle className="w-5 h-5 text-yellow-500" />
  }

  const getStatusColor = (status: string) => {
    if (status === 'healthy' || status === 'operational') {
      return 'text-green-500'
    } else if (status === 'unhealthy') {
      return 'text-red-500'
    }
    return 'text-yellow-500'
  }

  const envVars = [
    { name: 'NEXT_PUBLIC_BACKEND_URL', value: process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000', sensitive: false },
    { name: 'DATABASE_URL', value: '••••••••', sensitive: true },
    { name: 'OPENAI_API_KEY', value: '••••••••', sensitive: true },
    { name: 'JWT_SECRET', value: '••••••••', sensitive: true },
  ]

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Sistem Ayarları"
          description="Sistem durumu ve yapılandırma."
          actions={(
            <Button onClick={handleRefresh} disabled={refreshing} variant="outline">
              <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
              Yenile
            </Button>
          )}
        />

      {/* System Health */}
      <div className="bg-card border border-border/70 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-green-500/20 rounded-xl flex items-center justify-center">
            <Activity className="w-5 h-5 text-green-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-foreground">Sistem Durumu</h2>
            <p className="text-sm text-muted-foreground">Servis ve bileşen durumları</p>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary"></div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 bg-muted/40 rounded-xl">
              <div className="flex items-center justify-between mb-3">
                <Server className="w-5 h-5 text-muted-foreground" />
                {getStatusIcon(health?.api || 'unknown')}
              </div>
              <p className="text-foreground font-medium">API Sunucusu</p>
              <p className={`text-sm ${getStatusColor(health?.api || 'unknown')}`}>
                {health?.api === 'healthy' ? 'Çalışıyor' : 'Bilinmiyor'}
              </p>
            </div>

            <div className="p-4 bg-muted/40 rounded-xl">
              <div className="flex items-center justify-between mb-3">
                <Database className="w-5 h-5 text-muted-foreground" />
                {getStatusIcon(health?.database || 'unknown')}
              </div>
              <p className="text-foreground font-medium">Veritabanı</p>
              <p className={`text-sm ${getStatusColor(health?.database || 'unknown')}`}>
                {health?.database === 'healthy' ? 'Bağlı' : 'Bağlantı Yok'}
              </p>
            </div>

            <div className="p-4 bg-muted/40 rounded-xl">
              <div className="flex items-center justify-between mb-3">
                <Cpu className="w-5 h-5 text-muted-foreground" />
                {getStatusIcon(health?.status || 'unknown')}
              </div>
              <p className="text-foreground font-medium">Genel Durum</p>
              <p className={`text-sm ${getStatusColor(health?.status || 'unknown')}`}>
                {health?.status === 'operational' ? 'Operasyonel' : 'Bilinmiyor'}
              </p>
            </div>

            <div className="p-4 bg-muted/40 rounded-xl">
              <div className="flex items-center justify-between mb-3">
                <Activity className="w-5 h-5 text-muted-foreground" />
                <Check className="w-5 h-5 text-green-500" />
              </div>
              <p className="text-foreground font-medium">Uptime</p>
              <p className="text-sm text-green-500">{health?.uptime || 'N/A'}</p>
            </div>
          </div>
        )}
      </div>

      {/* Environment Variables */}
      <div className="bg-card border border-border/70 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center">
            <Settings className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-foreground">Yapılandırma</h2>
            <p className="text-sm text-muted-foreground">Ortam değişkenleri</p>
          </div>
        </div>

        <div className="space-y-3">
          {envVars.map((env, index) => (
            <div key={index} className="flex items-center justify-between p-4 bg-muted/40 rounded-xl">
              <div>
                <p className="text-foreground font-medium font-mono text-sm">{env.name}</p>
              </div>
              <div className="flex items-center gap-2">
                <code className="px-3 py-1 bg-muted rounded-lg text-sm text-foreground">
                  {env.value}
                </code>
                {env.sensitive && (
                  <span className="text-xs text-muted-foreground">(gizli)</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-card border border-border/70 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 bg-orange-500/20 rounded-xl flex items-center justify-center">
            <Cpu className="w-5 h-5 text-orange-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-foreground">Hızlı İşlemler</h2>
            <p className="text-sm text-muted-foreground">Sistem bakım işlemleri</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Button 
            variant="outline" 
            className="h-auto py-4 border-border/70 hover:bg-muted justify-start"
            onClick={() => toast({ title: 'Bilgi', description: 'Cache temizleme özelliği yakında eklenecek' })}
          >
            <div className="text-left">
              <p className="text-foreground font-medium">Cache Temizle</p>
              <p className="text-xs text-muted-foreground mt-1">Sistem önbelleğini temizle</p>
            </div>
          </Button>

          <Button 
            variant="outline" 
            className="h-auto py-4 border-border/70 hover:bg-muted justify-start"
            onClick={() => toast({ title: 'Bilgi', description: 'Log indirme özelliği yakında eklenecek' })}
          >
            <div className="text-left">
              <p className="text-foreground font-medium">Log İndir</p>
              <p className="text-xs text-muted-foreground mt-1">Sistem loglarını indir</p>
            </div>
          </Button>

          <Button 
            variant="outline" 
            className="h-auto py-4 border-border/70 hover:bg-muted justify-start"
            onClick={() => toast({ title: 'Bilgi', description: 'Yedekleme özelliği yakında eklenecek' })}
          >
            <div className="text-left">
              <p className="text-foreground font-medium">Yedekleme</p>
              <p className="text-xs text-muted-foreground mt-1">Veritabanı yedeği al</p>
            </div>
          </Button>
        </div>
      </div>

      {/* Version Info */}
      <div className="text-center text-sm text-muted-foreground">
        <p>SvontAi Admin Panel v1.0.0</p>
        <p>© 2024 SvontAi. Tüm hakları saklıdır.</p>
      </div>
      </div>
    </ContentContainer>
  )
}
