'use client'

import { useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Link2, RefreshCcw } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'
import { getApiErrorMessage } from '@/lib/api-error'
import { integrationsApi } from '@/lib/api'

type IntegrationState = 'connected' | 'missing' | 'expired'

type IntegrationStatusItem = {
  status: IntegrationState
  required_scopes?: string[]
  granted_scopes?: string[]
  expires_at?: string | null
  required?: boolean
  connectable?: boolean
  manageable?: boolean
  message?: string | null
}

type IntegrationStatusMap = Record<string, IntegrationStatusItem>

const TITLES: Record<string, string> = {
  google_drive: 'Google Drive',
  gmail: 'Gmail',
  openai: 'Yapay Zeka',
  google_sheets: 'Google Sheets',
  document_converter: 'Document Converter',
  whatsapp_cloud: 'WhatsApp Cloud',
  whatsapp_qr: 'WhatsApp QR',
  google_calendar: 'Google Calendar',
  n8n: 'n8n',
}

export default function IntegrationsPage() {
  const router = useRouter()
  const { toast } = useToast()
  const { data, isLoading, refetch, isFetching } = useQuery<IntegrationStatusMap>({
    queryKey: ['integrations-status'],
    queryFn: async () => {
      const response = await integrationsApi.getStatus()
      return response.data || {}
    },
  })

  const rows = useMemo(() => {
    const statusMap = data || {}
    return Object.keys(TITLES).map((key) => ({
      key,
      title: TITLES[key] || key,
      status: (statusMap[key]?.status || 'missing') as IntegrationState,
      requiredScopes: statusMap[key]?.required_scopes || [],
      grantedScopes: statusMap[key]?.granted_scopes || [],
      expiresAt: statusMap[key]?.expires_at || null,
      required: statusMap[key]?.required !== false,
      connectable: Boolean(statusMap[key]?.connectable),
      manageable: Boolean(statusMap[key]?.manageable),
      message: statusMap[key]?.message || null,
    }))
  }, [data])

  useEffect(() => {
    const handleOAuthMessage = (event: MessageEvent) => {
      if (event.data?.type !== 'GOOGLE_CALENDAR_CONNECTED' || !event.data?.success) return
      refetch()
      toast({
        title: 'Google bağlantısı tamamlandı',
        description: 'Drive, Gmail, Sheets ve Calendar izinleri güncellendi.',
      })
    }
    window.addEventListener('message', handleOAuthMessage)
    return () => window.removeEventListener('message', handleOAuthMessage)
  }, [refetch, toast])

  const handleConnect = async (key: string) => {
    try {
      if (key === 'whatsapp_cloud' || key === 'whatsapp_qr') {
        router.push('/dashboard/setup/whatsapp')
        return
      }
      if (key === 'google_drive' || key === 'gmail' || key === 'google_sheets' || key === 'google_calendar') {
        const response = await integrationsApi.startGoogleOAuth()
        const url = response.data?.auth_url
        if (!url) {
          throw new Error('Google OAuth URL alınamadı.')
        }
        const popup = window.open(url, 'svontai-google-oauth', 'width=620,height=760')
        if (!popup) throw new Error('Bağlantı penceresi tarayıcı tarafından engellendi.')
        return
      }
      toast({ title: 'Bu servis SvontAI tarafından otomatik yönetiliyor.' })
    } catch (error: any) {
      toast({
        title: 'Bağlantı başlatılamadı',
        description: getApiErrorMessage(error, 'Integrasyon bağlantısı başlatılamadı.'),
        variant: 'destructive',
      })
    }
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Entegrasyonlar"
          description="Tool’lar için gerekli bağlantıları yönetin."
          icon={<Icon3DBadge icon={Link2} from="from-primary" to="to-cyan-500" />}
          actions={
            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Yenile
            </Button>
          }
        />

        <Card>
          <CardHeader>
            <CardTitle>Bağlantı Durumu</CardTitle>
            <CardDescription>Google tek bağlantıyla, WhatsApp seçtiğiniz sağlayıcıyla çalışır.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading && <p className="text-sm text-muted-foreground">Yükleniyor...</p>}
            {!isLoading && rows.length === 0 && (
              <p className="text-sm text-muted-foreground">Integration verisi bulunamadı.</p>
            )}
            {rows.map((row) => (
              <div
                key={row.key}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 p-4"
              >
                <div className="flex items-center gap-3">
                  <p className="text-sm font-medium">{row.title}</p>
                  <Badge
                    variant={
                      row.status === 'connected'
                        ? 'success'
                        : row.status === 'expired'
                          ? 'warning'
                          : row.required
                            ? 'destructive'
                            : 'secondary'
                    }
                  >
                    {row.status === 'connected'
                      ? 'Bağlı'
                      : row.status === 'expired'
                        ? 'Süresi Doldu'
                        : row.required
                          ? 'Bağlantı Gerekli'
                          : 'İsteğe Bağlı'}
                  </Badge>
                </div>
                <div className="min-w-0 flex-1 sm:text-right">
                  {row.message && (
                    <p className="text-xs text-muted-foreground">{row.message}</p>
                  )}
                  {row.expiresAt && (
                    <p className="text-xs text-muted-foreground">
                      Token bitiş: {new Date(row.expiresAt).toLocaleString('tr-TR')}
                    </p>
                  )}
                </div>
                {(row.status === 'missing' || row.status === 'expired') && row.connectable ? (
                  <Button size="sm" onClick={() => handleConnect(row.key)}>
                    {row.status === 'expired' ? 'Tekrar Bağla' : 'Bağla'}
                  </Button>
                ) : row.status === 'connected' && row.manageable ? (
                  <Button size="sm" variant="outline" onClick={() => handleConnect(row.key)}>
                    Yönet
                  </Button>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </ContentContainer>
  )
}
