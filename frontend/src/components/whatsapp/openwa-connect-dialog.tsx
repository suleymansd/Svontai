'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { AlertTriangle, CheckCircle2, Loader2, QrCode, RefreshCw, Smartphone } from 'lucide-react'
import { onboardingApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { useToast } from '@/components/ui/use-toast'

type OpenWAStatus = {
  provider: 'openwa'
  session_id: string | null
  status: string
  connected: boolean
  phone_number: string | null
  push_name: string | null
  last_error: string | null
  qr_code?: string | null
}

type OpenWAConnectDialogProps = {
  enabled: boolean
  connected?: boolean
  providerStatus?: string | null
  onConnected: () => void
  triggerLabel?: string
}

const QR_REQUIRED_STATUSES = new Set([
  'qr_ready',
  'qr',
  'authentication_required',
  'logged_out',
])

export function OpenWAConnectDialog({
  enabled,
  connected = false,
  providerStatus = null,
  onConnected,
  triggerLabel = 'QR ile WhatsApp Bağla',
}: OpenWAConnectDialogProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [riskAccepted, setRiskAccepted] = useState(false)
  const notifiedConnectedRef = useRef(false)
  const recoveryAttemptedRef = useRef(false)

  const updateStatus = (data: OpenWAStatus) => {
    queryClient.setQueryData(['openwa-qr-status'], data)
    queryClient.invalidateQueries({ queryKey: ['whatsapp-onboarding-status'] })
  }

  const startMutation = useMutation({
    mutationFn: () => onboardingApi.startOpenWA(riskAccepted).then((response) => response.data as OpenWAStatus),
    onSuccess: updateStatus,
    onError: (error: unknown) => {
      toast({
        title: 'QR bağlantısı başlatılamadı',
        description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
        variant: 'destructive',
      })
    },
  })

  const reconnectMutation = useMutation({
    mutationFn: () => onboardingApi.reconnectOpenWA().then((response) => response.data as OpenWAStatus),
    onSuccess: updateStatus,
    onError: (error: unknown) => {
      toast({
        title: 'WhatsApp oturumu toparlanamadı',
        description: getApiErrorMessage(error, 'Yeni bir QR kodu üretmeyi deneyin.'),
        variant: 'destructive',
      })
    },
  })

  const refreshQrMutation = useMutation({
    mutationFn: () => onboardingApi.refreshOpenWAQr().then((response) => response.data as OpenWAStatus),
    onSuccess: (data) => {
      updateStatus(data)
      toast({
        title: 'Yeni QR kodu hazır',
        description: 'Telefonunuzdan bu yeni kodu tarayın.',
      })
    },
    onError: (error: unknown) => {
      toast({
        title: 'Yeni QR üretilemedi',
        description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
        variant: 'destructive',
      })
    },
  })

  const qrQuery = useQuery<OpenWAStatus>({
    queryKey: ['openwa-qr-status'],
    queryFn: () => onboardingApi.getOpenWAQr().then((response) => response.data as OpenWAStatus),
    enabled: open && enabled,
    refetchInterval: (query) => query.state.data?.connected ? false : 2500,
    retry: (failureCount, error) => {
      if (isAxiosError(error) && error.response?.status === 404) return false
      return failureCount < 2
    },
  })

  const hasNoSession = isAxiosError(qrQuery.error) && qrQuery.error.response?.status === 404
  const status = qrQuery.data || refreshQrMutation.data || reconnectMutation.data || startMutation.data
  const isConnected = qrQuery.isSuccess ? Boolean(qrQuery.data.connected) : connected
  const hasSession = !hasNoSession && Boolean(status?.session_id)
  const needsQr = QR_REQUIRED_STATUSES.has(status?.status || providerStatus || '')
  const isWorking = startMutation.isPending || reconnectMutation.isPending || refreshQrMutation.isPending

  useEffect(() => {
    if (!open) {
      recoveryAttemptedRef.current = false
      return
    }
    if (
      !status?.session_id
      || status.connected
      || status.qr_code
      || recoveryAttemptedRef.current
      || reconnectMutation.isPending
    ) return
    if (!QR_REQUIRED_STATUSES.has(status.status) && status.status !== 'disconnected' && status.status !== 'stopped') return

    recoveryAttemptedRef.current = true
    reconnectMutation.mutate()
  }, [open, reconnectMutation, status])

  useEffect(() => {
    if (!status?.connected || notifiedConnectedRef.current) return
    notifiedConnectedRef.current = true
    onConnected()
    toast({
      title: 'WhatsApp bağlandı',
      description: `${status.phone_number || 'Telefonunuz'} artık SvontAI ile çalışıyor.`,
    })
  }, [onConnected, status?.connected, status?.phone_number, toast])

  const openDialog = () => {
    notifiedConnectedRef.current = false
    recoveryAttemptedRef.current = false
    setOpen(true)
  }

  return (
    <>
      <Button
        onClick={openDialog}
        disabled={!enabled}
        className={connected && !needsQr ? 'bg-green-600 hover:bg-green-700' : undefined}
        variant={connected && !needsQr ? 'default' : needsQr ? 'destructive' : 'default'}
      >
        {connected && !needsQr ? (
          <CheckCircle2 className="mr-2 h-4 w-4" />
        ) : needsQr ? (
          <AlertTriangle className="mr-2 h-4 w-4" />
        ) : (
          <QrCode className="mr-2 h-4 w-4" />
        )}
        {connected && !needsQr ? 'Bağlantıyı Yönet' : needsQr ? 'QR ile Yeniden Bağla' : triggerLabel}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{isConnected ? 'WhatsApp bağlantısı' : 'Telefonunuzdan WhatsApp’ı bağlayın'}</DialogTitle>
            <DialogDescription>
              WhatsApp veya WhatsApp Business uygulamasında Bağlı Cihazlar bölümünden QR kodu tarayın.
            </DialogDescription>
          </DialogHeader>

          {qrQuery.isLoading && !status ? (
            <div className="flex min-h-48 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : isConnected ? (
            <div className="rounded-md border border-green-200 bg-green-50 p-5 text-center dark:border-green-900 dark:bg-green-950/30">
              <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-green-600" />
              <p className="font-semibold">Bağlantı hazır</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {status?.phone_number || 'WhatsApp hesabınız'} mesaj almaya hazır.
              </p>
              <p className="mt-3 text-xs text-muted-foreground">
                Telefonda oturum kapatılırsa SvontAI bunu algılar ve bu ekranda yeni QR kodunu hazırlar.
              </p>
            </div>
          ) : status?.qr_code ? (
            <div className="space-y-4">
              <div className="mx-auto w-fit rounded-md border bg-white p-3">
                <Image
                  src={status.qr_code}
                  alt="WhatsApp bağlantı QR kodu"
                  width={256}
                  height={256}
                  unoptimized
                />
              </div>
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Telefonunuzdaki onay bekleniyor
              </div>
            </div>
          ) : hasSession ? (
            <div className="space-y-4">
              <div className="rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-600" />
                  <div>
                    <p className="font-medium">Bağlantı yenilenmeli</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Oturum kapatılmış veya QR kodunun süresi dolmuş. Yeni QR oluşturup tekrar tarayın.
                    </p>
                  </div>
                </div>
              </div>
              {status?.last_error ? <p className="text-sm text-destructive">{status.last_error}</p> : null}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-md border p-4">
                <div className="flex items-start gap-3">
                  <Smartphone className="mt-0.5 h-5 w-5 text-green-600" />
                  <div>
                    <p className="font-medium">Normal WhatsApp ile de çalışır</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Meta şirket doğrulaması gerekmez. Geçici kopmalar otomatik toparlanır.
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
                <Checkbox
                  id="openwa-risk"
                  checked={riskAccepted}
                  onCheckedChange={(value) => setRiskAccepted(value === true)}
                />
                <Label htmlFor="openwa-risk" className="text-sm font-normal leading-5">
                  Bu QR bağlantısının Meta Cloud API olmadığını, bağlantı ve hesap kısıtlama risklerini içeren{' '}
                  <Link href="/openwa-consent" target="_blank" className="font-medium text-primary underline">
                    WhatsApp QR Risk Metni&apos;ni
                  </Link>{' '}
                  okudum ve kabul ediyorum.
                </Label>
              </div>

              {qrQuery.isError && !hasNoSession ? (
                <p className="text-sm text-destructive">
                  {getApiErrorMessage(qrQuery.error, 'QR durumu alınamadı.')}
                </p>
              ) : null}
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-2">
            {!hasSession && !isConnected ? (
              <Button
                onClick={() => startMutation.mutate()}
                disabled={!riskAccepted || isWorking}
              >
                {startMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <QrCode className="mr-2 h-4 w-4" />}
                QR Oluştur
              </Button>
            ) : null}
            {hasSession && !isConnected && !status?.qr_code ? (
              <Button onClick={() => reconnectMutation.mutate()} disabled={isWorking}>
                {reconnectMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                Oturumu Toparla
              </Button>
            ) : null}
            {hasSession && !isConnected ? (
              <Button variant="outline" onClick={() => refreshQrMutation.mutate()} disabled={isWorking}>
                {refreshQrMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <QrCode className="mr-2 h-4 w-4" />}
                Yeni QR
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => setOpen(false)}>Kapat</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
