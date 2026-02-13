'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { LifeBuoy, Filter } from 'lucide-react'
import { ticketsApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { FilterBar } from '@/components/shared/filter-bar'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface Ticket {
  id: string
  subject: string
  status: string
  priority: string
  tenant_id: string
  created_at: string
  last_activity_at: string
}

export default function AdminTicketsPage() {
  const router = useRouter()
  const [statusFilter, setStatusFilter] = useState<string | undefined>()

  const { data: tickets, isLoading } = useQuery<Ticket[]>({
    queryKey: ['admin-tickets', statusFilter],
    queryFn: () => ticketsApi.list({ skip: 0, limit: 50, status: statusFilter }).then(res => res.data),
  })

  const columns: DataColumn<Ticket>[] = useMemo(() => [
    {
      key: 'subject',
      header: 'Konu',
      render: (row) => (
        <div className="space-y-1">
          <p className="font-medium">{row.subject}</p>
          <p className="text-xs text-muted-foreground">#{row.id.slice(0, 8)}</p>
        </div>
      ),
    },
    {
      key: 'tenant',
      header: 'Tenant',
      render: (row) => <span className="text-xs text-muted-foreground">{row.tenant_id}</span>,
    },
    {
      key: 'priority',
      header: 'Öncelik',
      render: (row) => <Badge variant="outline">{row.priority}</Badge>,
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <Badge variant={row.status === 'solved' ? 'success' : row.status === 'pending' ? 'warning' : 'secondary'}>
          {row.status}
        </Badge>
      ),
    },
    {
      key: 'updated',
      header: 'Son Aktivite',
      render: (row) => new Date(row.last_activity_at).toLocaleString('tr-TR'),
    },
  ], [])

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Tickets"
          description="Destek taleplerini ve SLA akışlarını yönetin."
        />

        <FilterBar
          searchPlaceholder="Ticket ara..."
          onSearchChange={() => {}}
          actions={(
            <Button variant="outline" size="sm" onClick={() => setStatusFilter(undefined)}>
              <Filter className="h-4 w-4 mr-2" />
              Filtreleri Temizle
            </Button>
          )}
        />

        <DataTable
          columns={columns}
          data={tickets || []}
          loading={isLoading}
          onRowClick={(row) => router.push(`/admin/tickets/${row.id}`)}
          emptyState={(
            <EmptyState
              icon={<LifeBuoy className="h-6 w-6 text-primary" />}
              title="Ticket yok"
              description="Destek talepleri burada listelenecek."
            />
          )}
        />
      </div>
    </ContentContainer>
  )
}
