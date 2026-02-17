'use client'

import { useMemo } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, PhoneCall, FileText, MessageSquare } from 'lucide-react'
import { callsApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

type CallRow = {
  id: string
  provider: string
  provider_call_id: string
  direction: string
  status: string
  from_number: string
  to_number: string
  duration_seconds: number
  created_at: string
}

type TranscriptRow = {
  id: string
  segment_index: number
  speaker: string
  text: string
  ts_iso?: string | null
}

type SummaryRow = {
  id: string
  intent?: string | null
  summary: string
  labels_json: Record<string, any>
  action_items_json: Record<string, any>
  updated_at: string
}

export default function CallDetailPage() {
  const params = useParams<{ callId: string }>()
  const callId = Array.isArray(params.callId) ? params.callId[0] : params.callId

  const { data: call, isLoading: callLoading } = useQuery<CallRow>({
    queryKey: ['call', callId],
    queryFn: () => callsApi.get(callId).then((res) => res.data),
    enabled: Boolean(callId),
  })

  const { data: transcript } = useQuery<TranscriptRow[]>({
    queryKey: ['call-transcript', callId],
    queryFn: () => callsApi.transcript(callId).then((res) => res.data),
    enabled: Boolean(callId),
  })

  const { data: summary } = useQuery<SummaryRow>({
    queryKey: ['call-summary', callId],
    queryFn: () => callsApi.summary(callId).then((res) => res.data),
    enabled: Boolean(callId),
    retry: false,
  })

  const durationLabel = useMemo(() => {
    const seconds = call?.duration_seconds || 0
    const minutes = Math.floor(seconds / 60)
    const rem = seconds % 60
    if (minutes <= 0) return `${seconds}s`
    return `${minutes}dk ${rem}s`
  }, [call?.duration_seconds])

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Çağrı Detayı"
          description={call ? `${call.from_number} → ${call.to_number}` : 'Yükleniyor...'}
          icon={<Icon3DBadge icon={PhoneCall} from="from-emerald-500" to="to-cyan-500" />}
          actions={(
            <Link href="/dashboard/calls">
              <Button variant="outline" type="button">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Aramalara dön
              </Button>
            </Link>
          )}
        />

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-muted-foreground" />
              Özet
            </CardTitle>
            <CardDescription>n8n call workflow summary callback ile dolar.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {callLoading ? (
              <div className="text-sm text-muted-foreground">Yükleniyor...</div>
            ) : call ? (
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{call.provider}</Badge>
                <Badge variant="outline">{call.direction}</Badge>
                <Badge variant={call.status === 'completed' ? 'success' : 'secondary'}>{call.status}</Badge>
                <Badge variant="outline">{durationLabel}</Badge>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">Çağrı bulunamadı.</div>
            )}

            {summary ? (
              <div className="space-y-3">
                {summary.intent && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Intent: </span>
                    <span className="font-medium">{summary.intent}</span>
                  </div>
                )}
                <div className="rounded-xl border border-border/70 bg-muted/20 p-4 text-sm whitespace-pre-wrap">
                  {summary.summary}
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">
                Özet henüz yok (workflow callback bekleniyor).
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-muted-foreground" />
              Transcript
            </CardTitle>
            <CardDescription>Voice Intent sırasında segmentler kaydedilir.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {!transcript || transcript.length === 0 ? (
              <div className="text-sm text-muted-foreground">Transcript yok.</div>
            ) : (
              <div className="space-y-2">
                {transcript.map((row) => (
                  <div
                    key={row.id}
                    className="rounded-xl border border-border/70 bg-card/60 p-3 text-sm"
                  >
                    <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">{row.speaker}</span>
                      <span>{row.ts_iso ? new Date(row.ts_iso).toLocaleString('tr-TR') : ''}</span>
                    </div>
                    <div className="whitespace-pre-wrap">{row.text}</div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </ContentContainer>
  )
}

