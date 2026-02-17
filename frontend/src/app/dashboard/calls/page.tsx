'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { PhoneCall, Filter } from 'lucide-react'
import { callsApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { FilterBar } from '@/components/shared/filter-bar'
import { EmptyState } from '@/components/shared/empty-state'
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
  started_at?: string | null
  ended_at?: string | null
  duration_seconds: number
  created_at: string
}

export default function CallsPage() {
  const router = useRouter()
  const [status, setStatus] = useState<string>('')

  const { data, isLoading } = useQuery<CallRow[]>({
    queryKey: ['calls', status],
    queryFn: () => callsApi.list({ limit: 100, status: status || undefined }).then((res) => res.data),
  })

  const columns: DataColumn<CallRow>[] = useMemo(
    () => [
      {
        key: 'from_number',
        header: 'Arayan',
        render: (row) => (
          <div className="space-y-1">
            <div className="text-sm font-medium">{row.from_number}</div>
            <div className="text-xs text-muted-foreground">{row.provider}</div>
          </div>
        ),
      },
      {
        key: 'status',
        header: 'Durum',
        render: (row) => (
          <Badge variant={row.status === 'completed' ? 'success' : row.status === 'failed' ? 'destructive' : 'secondary'}>
            {row.status}
          </Badge>
        ),
      },
      {
        key: 'direction',
        header: 'Yön',
        render: (row) => <Badge variant="outline">{row.direction}</Badge>,
      },
      {
        key: 'duration_seconds',
        header: 'Süre',
        render: (row) => (
          <span className="text-sm text-muted-foreground">
            {Math.round((row.duration_seconds || 0) / 60)} dk
          </span>
        ),
      },
      {
        key: 'created_at',
        header: 'Tarih',
        render: (row) => (
          <span className="text-sm text-muted-foreground">
            {new Date(row.created_at).toLocaleString('tr-TR')}
          </span>
        ),
      },
    ],
    []
  )

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Aramalar"
          description="Voice AI Agent çağrı loglarını ve özetleri görüntüleyin."
          icon={<Icon3DBadge icon={PhoneCall} from="from-emerald-500" to="to-cyan-500" />}
        />

        <FilterBar
          searchPlaceholder="Arama / filtre yakında"
          onSearchChange={() => {}}
          actions={(
            <Button variant="outline" size="sm" onClick={() => setStatus('')}>
              <Filter className="h-4 w-4 mr-2" />
              Filtreyi Sıfırla
            </Button>
          )}
        />

        <DataTable
          columns={columns}
          data={data || []}
          loading={isLoading}
          onRowClick={(row) => router.push(`/dashboard/calls/${row.id}`)}
          emptyState={(
            <EmptyState
              icon={<PhoneCall className="h-6 w-6 text-primary" />}
              title="Henüz çağrı yok"
              description="Voice Gateway üzerinden çağrı geldiğinde burada listelenecek."
            />
          )}
        />
      </div>
    </ContentContainer>
  )
}

