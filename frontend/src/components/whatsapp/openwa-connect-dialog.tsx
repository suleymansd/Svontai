'use client'

import Image from 'next/image'
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2, Loader2, QrCode, RefreshCw, Smartphone } from 'lucide-react'
import { onboardingApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { Badge } from '@/components/ui/badge'
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
  onConnected: () => void
  triggerLabel?: string
}

export function OpenWAConnectDialog({
  enabled,
  connected = false,
  onConnected,
  triggerLabel = 'QR ile WhatsApp Bağla',
}: OpenWAConnectDialogProps) {
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [riskAccepted, setRiskAccepted] = useState(false)
  const [sessionStarted, setSessionStarted] = useState(false)
  const notifiedConnectedRef = useRef(false)

  const startMutation = useMutation({
    mutationFn: () => onboardingApi.startOpenWA(riskAccepted).then((response) => response.data as OpenWAStatus),
    onSuccess: (data) => {
      setSessionStarted(true)
      if (data.connected) {
        notifiedConnectedRef.current = true
        onConnected()
      }
    },
    onError: (error: unknown) => {
      toast({
        title: 'QR bağlantısı başlatılamadı',
        description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
        variant: 'destructive',
      })
    },
  })

  const qrQuery = useQuery<OpenWAStatus>({
    queryKey: ['openwa-qr-status'],
    queryFn: () => onboardingApi.getOpenWAQr().then((response) => response.data as OpenWAStatus),
    enabled: open && sessionStarted,
    refetchInterval: (query) => query.state.data?.connected ? false : 2000,
    retry: 2,
  })

  useEffect(() => {
    if (!qrQuery.data?.connected || notifiedConnectedRef.current) return
    notifiedConnectedRef.current = true
    onConnected()
    toast({
      title: 'WhatsApp bağlandı',
      description: `${qrQuery.data.phone_number || 'Telefonunuz'} artık SmartWA ile çalışıyor.`,
    })
  }, [onConnected, qrQuery.data?.connected, qrQuery.data?.phone_number, toast])

  const status = qrQuery.data || startMutation.data
  const isConnected = connected || Boolean(status?.connected)

  return (
    <>
      <Button
        onClick={() => setOpen(true)}
        disabled={!enabled || connected}
        className="bg-green-600 hover:bg-green-700"
      >
        {connected ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <QrCode className="mr-2 h-4 w-4" />}
        {connected ? 'WhatsApp Bağlı' : triggerLabel}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Telefonunuzdan WhatsApp’ı bağlayın</DialogTitle>
            <DialogDescription>
              WhatsApp veya WhatsApp Business uygulamasında Bağlı Cihazlar bölümünden QR kodu tarayın.
            </DialogDescription>
          </DialogHeader>

          {isConnected ? (
            <div className="rounded-md border border-green-200 bg-green-50 p-5 text-center dark:border-green-900 dark:bg-green-950/30">
              <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-green-600" />
              <p className="font-semibold">Bağlantı hazır</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {status?.phone_number || 'WhatsApp hesabınız'} mesaj almaya hazır.
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
          ) : (
            <div className="space-y-4">
              <div className="rounded-md border p-4">
                <div className="flex items-start gap-3">
                  <Smartphone className="mt-0.5 h-5 w-5 text-green-600" />
                  <div>
                    <p className="font-medium">Normal WhatsApp ile de çalışır</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Meta şirket doğrulaması gerekmez. Bağlantı açık kaldığı sürece sistem mesajları otomatik işler.
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
                  Bu QR bağlantısının Meta Cloud API olmadığını ve WhatsApp’ın hesap kısıtlaması uygulayabileceğini kabul ediyorum.
                </Label>
              </div>

              {status?.last_error ? (
                <p className="text-sm text-destructive">{status.last_error}</p>
              ) : null}
              {qrQuery.isError ? (
                <p className="text-sm text-destructive">
                  QR durumu alınamadı. Bağlantıyı yenileyin veya tekrar başlatın.
                </p>
              ) : null}
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            {!sessionStarted && !isConnected ? (
              <Button
                onClick={() => startMutation.mutate()}
                disabled={!riskAccepted || startMutation.isPending}
              >
                {startMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <QrCode className="mr-2 h-4 w-4" />
                )}
                QR Oluştur
              </Button>
            ) : null}
            {sessionStarted && !isConnected && !status?.qr_code ? (
              <Button variant="outline" onClick={() => qrQuery.refetch()} disabled={qrQuery.isFetching}>
                <RefreshCw className={`mr-2 h-4 w-4 ${qrQuery.isFetching ? 'animate-spin' : ''}`} />
                Yenile
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => setOpen(false)}>Kapat</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
