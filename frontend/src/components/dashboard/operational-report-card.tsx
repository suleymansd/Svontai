'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, FileText, Loader2, Share2 } from 'lucide-react'
import { analyticsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'

type OperationalReport = {
  period: 'today' | 'week'
  title: string
  summary: string
  text: string
  generated_at: string
  metrics: {
    incoming_messages: number
    ai_replies: number
    response_rate: number
    leads: number
    appointments: number
    failed_automations: number
  }
}

export function OperationalReportCard() {
  const { toast } = useToast()
  const [period, setPeriod] = useState<'today' | 'week'>('today')
  const { data, isLoading } = useQuery<OperationalReport>({
    queryKey: ['operational-report', period],
    queryFn: () => analyticsApi.getOperationalReport(period).then((response) => response.data),
  })

  const shareToNotes = async () => {
    if (!data) return
    try {
      const filename = `svontai-${period === 'today' ? 'gunluk' : 'haftalik'}-rapor.txt`
      const file = new File([data.text], filename, { type: 'text/plain' })
      if (navigator.share) {
        const shareData: ShareData = { title: data.title, text: data.summary }
        if (navigator.canShare?.({ files: [file] })) {
          shareData.files = [file]
        } else {
          shareData.text = data.text
        }
        await navigator.share(shareData)
        return
      }
      await navigator.clipboard.writeText(data.text)
      toast({
        title: 'Rapor panoya kopyalandı',
        description: 'Telefonunuzdaki Notlar uygulamasına yapıştırabilirsiniz.',
      })
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      toast({
        title: 'Rapor paylaşılamadı',
        description: 'Tarayıcı paylaşım menüsünü açamadı.',
        variant: 'destructive',
      })
    }
  }

  return (
    <Card className="border border-border/70 shadow-soft">
      <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            Operasyon Raporu
          </CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Gerçek mesaj, yanıt, müşteri ve randevu kayıtlarından oluşturulur.
          </p>
        </div>
        <div className="flex rounded-lg border p-1">
          <Button
            size="sm"
            variant={period === 'today' ? 'default' : 'ghost'}
            onClick={() => setPeriod('today')}
          >
            Bugün
          </Button>
          <Button
            size="sm"
            variant={period === 'week' ? 'default' : 'ghost'}
            onClick={() => setPeriod('week')}
          >
            Son 7 Gün
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading || !data ? (
          <div className="flex h-28 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Gelen Mesaj</p>
                <p className="mt-1 text-xl font-semibold">{data.metrics.incoming_messages}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">AI Yanıtı</p>
                <p className="mt-1 text-xl font-semibold">{data.metrics.ai_replies}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Yeni Müşteri</p>
                <p className="mt-1 text-xl font-semibold">{data.metrics.leads}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Randevu</p>
                <p className="mt-1 text-xl font-semibold">{data.metrics.appointments}</p>
              </div>
            </div>
            <div className="flex flex-col gap-4 rounded-lg border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                <div>
                  <p className="font-medium">{data.summary}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Yanıt oranı %{data.metrics.response_rate}
                  </p>
                </div>
              </div>
              <Button onClick={shareToNotes}>
                <Share2 className="mr-2 h-4 w-4" />
                Notlar’a Aktar
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
