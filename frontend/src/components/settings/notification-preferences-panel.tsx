'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BellRing, CheckCircle2, Loader2, Smartphone } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'
import { getApiErrorMessage } from '@/lib/api-error'
import { notificationsApi } from '@/lib/api'

type Preferences = {
  notify_ai_reply: boolean
  notify_new_lead: boolean
  notify_appointment: boolean
  notify_weekly_report: boolean
}

type NotificationSettings = {
  configured: boolean
  public_key: string
  subscribed: boolean
  device_count: number
  preferences: Preferences
}

const preferenceRows: Array<{ key: keyof Preferences; title: string; description: string }> = [
  {
    key: 'notify_ai_reply',
    title: 'SvontAI çalışıyor',
    description: 'Müşteri mesajı otomatik yanıtlandığında',
  },
  {
    key: 'notify_new_lead',
    title: 'Yeni müşteri',
    description: 'Yeni bir potansiyel müşteri oluştuğunda',
  },
  {
    key: 'notify_appointment',
    title: 'Yeni randevu',
    description: 'SvontAI bir randevu oluşturduğunda',
  },
  {
    key: 'notify_weekly_report',
    title: 'Haftalık rapor',
    description: 'Haftalık operasyon özeti hazır olduğunda',
  },
]

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const output = new Uint8Array(rawData.length)
  for (let index = 0; index < rawData.length; index += 1) {
    output[index] = rawData.charCodeAt(index)
  }
  return output
}

export function NotificationPreferencesPanel() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery<NotificationSettings>({
    queryKey: ['notification-settings'],
    queryFn: () => notificationsApi.getSettings().then((response) => response.data),
  })

  const enableMutation = useMutation({
    mutationFn: async () => {
      if (!data?.configured || !data.public_key) {
        throw new Error('Bildirim servisi henüz sunucuda etkinleştirilmedi.')
      }
      if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
        throw new Error('Bu cihaz bildirim özelliğini desteklemiyor.')
      }
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        throw new Error('Bildirim izni verilmedi.')
      }
      const registration = await navigator.serviceWorker.ready
      let subscription = await registration.pushManager.getSubscription()
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(data.public_key),
        })
      }
      await notificationsApi.subscribe(subscription.toJSON())
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['notification-settings'] })
      toast({
        title: 'Telefon bildirimleri açık',
        description: 'SvontAI müşteri mesajlarını yanıtladığında cihazınıza bilgi verecek.',
      })
    },
    onError: (error) => {
      toast({
        title: 'Bildirim açılamadı',
        description: getApiErrorMessage(error, error instanceof Error ? error.message : 'Bildirim açılamadı.'),
        variant: 'destructive',
      })
    },
  })

  const disableMutation = useMutation({
    mutationFn: async () => {
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()
      const endpoint = subscription?.endpoint
      if (subscription) await subscription.unsubscribe()
      await notificationsApi.unsubscribe(endpoint)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['notification-settings'] })
      toast({ title: 'Telefon bildirimleri kapatıldı' })
    },
  })

  const preferencesMutation = useMutation({
    mutationFn: (preferences: Preferences) => notificationsApi.updateSettings(preferences),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notification-settings'] }),
    onError: (error) => {
      toast({
        title: 'Bildirim tercihi kaydedilemedi',
        description: getApiErrorMessage(error, 'Bildirim tercihi kaydedilemedi.'),
        variant: 'destructive',
      })
    },
  })

  const preferences = data?.preferences || {
    notify_ai_reply: true,
    notify_new_lead: true,
    notify_appointment: true,
    notify_weekly_report: true,
  }
  const isIos = typeof navigator !== 'undefined' && /iphone|ipad|ipod/i.test(navigator.userAgent)
  const isStandalone = typeof window !== 'undefined'
    && (window.matchMedia('(display-mode: standalone)').matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Telefon Bildirimleri</CardTitle>
        <CardDescription>SvontAI iş yaptığında iOS ve Android cihazınıza durum bildirir.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-col gap-4 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              {data?.subscribed ? (
                <CheckCircle2 className="h-5 w-5 text-success" />
              ) : (
                <Smartphone className="h-5 w-5 text-primary" />
              )}
            </div>
            <div>
              <p className="font-medium">
                {data?.subscribed ? 'Bu cihaz bağlı' : 'Bu cihazı SvontAI’ye bağla'}
              </p>
              <p className="text-sm text-muted-foreground">
                {data?.subscribed
                  ? `${data.device_count} cihaz bildirim alıyor.`
                  : 'Otomatik yanıt ve operasyon bilgileri telefonunuza gelsin.'}
              </p>
              {isIos && !isStandalone && (
                <p className="mt-2 text-xs text-warning">
                  iPhone bildirimleri için SvontAI ana ekrana eklenmelidir.
                </p>
              )}
            </div>
          </div>
          {data?.subscribed ? (
            <Button
              variant="outline"
              onClick={() => disableMutation.mutate()}
              disabled={disableMutation.isPending}
            >
              Bildirimleri Kapat
            </Button>
          ) : (
            <Button
              onClick={() => enableMutation.mutate()}
              disabled={isLoading || enableMutation.isPending || !data?.configured}
            >
              {enableMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <BellRing className="mr-2 h-4 w-4" />
              )}
              Telefonda Bildirimleri Aç
            </Button>
          )}
        </div>

        <div className="divide-y rounded-lg border">
          {preferenceRows.map((item) => (
            <div key={item.key} className="flex items-center justify-between gap-4 p-4">
              <div>
                <p className="text-sm font-medium">{item.title}</p>
                <p className="text-xs text-muted-foreground">{item.description}</p>
              </div>
              <Switch
                checked={preferences[item.key]}
                disabled={!data?.subscribed || preferencesMutation.isPending}
                onCheckedChange={(checked) => {
                  preferencesMutation.mutate({ ...preferences, [item.key]: checked })
                }}
              />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
