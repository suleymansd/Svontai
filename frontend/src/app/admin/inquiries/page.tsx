'use client'

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Inbox, Mail } from 'lucide-react'

import { adminApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { DataColumn, DataTable } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { PageHeader } from '@/components/shared/page-header'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { useToast } from '@/components/ui/use-toast'

type InquiryStatus = 'new' | 'contacted' | 'qualified' | 'closed' | 'spam'

interface SalesInquiry {
  id: string
  name: string
  email: string
  company: string | null
  phone: string | null
  plan: string | null
  interval: string | null
  message: string
  status: InquiryStatus
  email_delivered: boolean
  created_at: string
}

const statusLabels: Record<InquiryStatus, string> = {
  new: 'Yeni',
  contacted: 'İletişime Geçildi',
  qualified: 'Uygun Müşteri',
  closed: 'Kapandı',
  spam: 'Spam',
}

export default function AdminInquiriesPage() {
  const [search, setSearch] = useState('')
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { data, isLoading } = useQuery<{ items: SalesInquiry[]; total: number }>({
    queryKey: ['admin-sales-inquiries', search],
    queryFn: () => adminApi.listSalesInquiries({ search: search || undefined }).then((response) => response.data),
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: InquiryStatus }) => adminApi.updateSalesInquiry(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-sales-inquiries'] })
      toast({ title: 'Talep durumu güncellendi' })
    },
  })

  const columns: DataColumn<SalesInquiry>[] = useMemo(() => [
    {
      key: 'customer',
      header: 'Müşteri',
      render: (row) => (
        <div className="space-y-1">
          <p className="font-medium">{row.name}</p>
          <a className="text-xs text-primary hover:underline" href={`mailto:${row.email}`}>{row.email}</a>
          <p className="text-xs text-muted-foreground">{row.company || row.phone || '-'}</p>
        </div>
      ),
    },
    {
      key: 'request',
      header: 'Talep',
      render: (row) => (
        <div className="max-w-md space-y-1">
          <Badge variant="outline">{row.plan || 'Genel'} {row.interval || ''}</Badge>
          <p className="line-clamp-3 text-sm text-muted-foreground">{row.message}</p>
        </div>
      ),
    },
    {
      key: 'delivery',
      header: 'Bildirim',
      render: (row) => (
        <Badge variant={row.email_delivered ? 'success' : 'warning'}>
          {row.email_delivered ? 'E-posta gönderildi' : 'Panel kaydı'}
        </Badge>
      ),
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <select
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          value={row.status}
          onChange={(event) => updateMutation.mutate({ id: row.id, status: event.target.value as InquiryStatus })}
          disabled={updateMutation.isPending}
          aria-label={`${row.name} talep durumu`}
        >
          {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      ),
    },
    {
      key: 'created_at',
      header: 'Oluşturuldu',
      render: (row) => new Date(row.created_at).toLocaleString('tr-TR'),
    },
  ], [updateMutation])

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Satış Talepleri"
          description="Web sitesi ve plan görüşmesi taleplerini takip edin."
          icon={<Icon3DBadge icon={Inbox} from="from-emerald-500" to="to-cyan-500" />}
        />
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="İsim, e-posta veya işletme ara..."
          className="max-w-md"
        />
        <DataTable
          columns={columns}
          data={data?.items || []}
          loading={isLoading}
          emptyState={<EmptyState icon={<Mail className="h-6 w-6 text-primary" />} title="Satış talebi yok" />}
        />
      </div>
    </ContentContainer>
  )
}
