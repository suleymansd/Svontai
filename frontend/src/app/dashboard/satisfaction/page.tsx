'use client'

import { useMemo, useState } from 'react'
import { MessageSquareText, Plus, Smile } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'
import { KPIStat } from '@/components/shared/kpi-stat'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type SurveyStatus = 'scheduled' | 'sent' | 'completed'

interface SatisfactionSurvey {
  id: string
  customer: string
  channel: 'WhatsApp' | 'Email' | 'SMS'
  template: 'CSAT' | 'NPS' | 'CES'
  sentAt: string
  status: SurveyStatus
  score?: number | null
  comment?: string
}

const initialSurveys: SatisfactionSurvey[] = [
  {
    id: 'csat-001',
    customer: 'Derya Aksoy',
    channel: 'WhatsApp',
    template: 'CSAT',
    sentAt: '2026-02-03 16:20',
    status: 'completed',
    score: 5,
    comment: 'Hızlı dönüş ve net bilgilendirme.',
  },
  {
    id: 'csat-002',
    customer: 'Melis Kaya',
    channel: 'Email',
    template: 'NPS',
    sentAt: '2026-02-04 10:05',
    status: 'sent',
    score: null,
    comment: '',
  },
  {
    id: 'csat-003',
    customer: 'Erdem Demir',
    channel: 'SMS',
    template: 'CSAT',
    sentAt: '2026-02-06 09:30',
    status: 'scheduled',
    score: null,
    comment: '',
  },
]

const statusLabels: Record<SurveyStatus, string> = {
  scheduled: 'Planlandı',
  sent: 'Gönderildi',
  completed: 'Yanıtlandı',
}

const statusVariant: Record<SurveyStatus, 'warning' | 'info' | 'success'> = {
  scheduled: 'warning',
  sent: 'info',
  completed: 'success',
}

const formatDateTime = (value: string) => (value ? value.replace('T', ' ') : '')

export default function SatisfactionPage() {
  const [surveys, setSurveys] = useState<SatisfactionSurvey[]>(initialSurveys)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    customer: '',
    channel: 'WhatsApp' as SatisfactionSurvey['channel'],
    template: 'CSAT' as SatisfactionSurvey['template'],
    scheduleAt: '',
  })

  const completedCount = surveys.filter((survey) => survey.status === 'completed').length
  const totalCount = surveys.length
  const averageScore = useMemo(() => {
    const completed = surveys.filter((survey) => typeof survey.score === 'number')
    if (completed.length === 0) return '-'
    const total = completed.reduce((sum, survey) => sum + (survey.score ?? 0), 0)
    return (total / completed.length).toFixed(1)
  }, [surveys])
  const responseRate = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  const columns: DataColumn<SatisfactionSurvey>[] = useMemo(() => [
    {
      key: 'customer',
      header: 'Müşteri',
      render: (row) => <span className="font-medium">{row.customer}</span>,
    },
    {
      key: 'channel',
      header: 'Kanal',
      render: (row) => <Badge variant="outline">{row.channel}</Badge>,
    },
    {
      key: 'template',
      header: 'Şablon',
      render: (row) => <span className="text-sm">{row.template}</span>,
    },
    {
      key: 'sentAt',
      header: 'Gönderim',
      render: (row) => <span className="text-sm text-muted-foreground">{row.sentAt}</span>,
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <Badge variant={statusVariant[row.status]}>
          {statusLabels[row.status]}
        </Badge>
      ),
    },
    {
      key: 'score',
      header: 'Skor',
      render: (row) => {
        if (row.score == null) {
          return <span className="text-sm text-muted-foreground">-</span>
        }
        const scale = row.template === 'NPS' ? 10 : row.template === 'CES' ? 7 : 5
        const variant = row.score >= Math.ceil(scale * 0.8) ? 'success' : row.score >= Math.ceil(scale * 0.6) ? 'warning' : 'destructive'
        return <Badge variant={variant}>{row.score}/{scale}</Badge>
      },
    },
    {
      key: 'comment',
      header: 'Yorum',
      render: (row) => (
        <span className="text-sm text-muted-foreground">
          {row.comment && row.comment.length > 0 ? row.comment : '—'}
        </span>
      ),
    },
  ], [])

  const handleSendSurvey = () => {
    const sentAt = formatDateTime(form.scheduleAt) || new Date().toISOString().slice(0, 16).replace('T', ' ')
    const isScheduled = Boolean(form.scheduleAt) && new Date(form.scheduleAt) > new Date()
    const next: SatisfactionSurvey = {
      id: `csat-${String(surveys.length + 1).padStart(3, '0')}`,
      customer: form.customer || 'Yeni Müşteri',
      channel: form.channel,
      template: form.template,
      sentAt,
      status: isScheduled ? 'scheduled' : 'sent',
      score: null,
      comment: '',
    }
    setSurveys((prev) => [next, ...prev])
    setForm({
      customer: '',
      channel: 'WhatsApp',
      template: 'CSAT',
      scheduleAt: '',
    })
    setOpen(false)
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Memnuniyet Değerlendirme"
          description="Memnuniyet ölçer tool’u ile gönderilen anketleri ve sonuçları izleyin."
          actions={(
            <Button onClick={() => setOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Anket Gönder
            </Button>
          )}
        />

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KPIStat label="Gönderilen" value={totalCount} icon={<MessageSquareText className="h-5 w-5" />} />
          <KPIStat label="Yanıtlanan" value={completedCount} icon={<Smile className="h-5 w-5" />} />
          <KPIStat label="Ortalama Skor" value={averageScore} icon={<Smile className="h-5 w-5" />} />
          <KPIStat label="Yanıt Oranı" value={totalCount > 0 ? `%${responseRate}` : '-'} icon={<MessageSquareText className="h-5 w-5" />} />
        </div>

        <DataTable
          columns={columns}
          data={surveys}
          loading={false}
          emptyState={(
            <EmptyState
              icon={<Smile className="h-6 w-6 text-primary" />}
              title="Memnuniyet anketi yok"
              description="Yeni bir anket göndererek geri bildirim toplayın."
              action={(
                <Button onClick={() => setOpen(true)}>Anket Gönder</Button>
              )}
            />
          )}
        />
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg glass-card">
          <DialogHeader>
            <DialogTitle>Memnuniyet Anketi Gönder</DialogTitle>
            <DialogDescription>Müşteriye kısa bir memnuniyet anketi iletin.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="survey-customer">Müşteri</Label>
              <Input
                id="survey-customer"
                value={form.customer}
                onChange={(event) => setForm((prev) => ({ ...prev, customer: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label>Kanal</Label>
              <Select value={form.channel} onValueChange={(value) => setForm((prev) => ({ ...prev, channel: value as SatisfactionSurvey['channel'] }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Kanal seçin" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="WhatsApp">WhatsApp</SelectItem>
                  <SelectItem value="Email">Email</SelectItem>
                  <SelectItem value="SMS">SMS</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Şablon</Label>
              <Select value={form.template} onValueChange={(value) => setForm((prev) => ({ ...prev, template: value as SatisfactionSurvey['template'] }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Şablon seçin" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CSAT">CSAT (1-5)</SelectItem>
                  <SelectItem value="NPS">NPS (0-10)</SelectItem>
                  <SelectItem value="CES">CES (1-7)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="survey-schedule">Gönderim zamanı</Label>
              <Input
                id="survey-schedule"
                type="datetime-local"
                value={form.scheduleAt}
                onChange={(event) => setForm((prev) => ({ ...prev, scheduleAt: event.target.value }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Vazgeç</Button>
            <Button onClick={handleSendSurvey} className="bg-gradient-to-r from-blue-600 to-violet-600 btn-shimmer">Gönder</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer >
  )
}
