'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Filter, ListChecks } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { FilterBar } from '@/components/shared/filter-bar'
import { EmptyState } from '@/components/shared/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { adminApi } from '@/lib/api'

export default function AuditPage() {
  const [actionFilter, setActionFilter] = useState<string | undefined>()

  const { data: logs, isLoading } = useQuery({
    queryKey: ['audit-logs', actionFilter],
    queryFn: () => adminApi.listAuditLogs({ skip: 0, limit: 50, action: actionFilter }).then(res => res.data),
  })

  const columns: DataColumn<any>[] = [
    { key: 'action', header: 'Aksiyon', render: (row) => <span className="font-medium">{row.action}</span> },
    { key: 'tenant_id', header: 'Tenant', render: (row) => <span className="text-xs text-muted-foreground">{row.tenant_id || 'global'}</span> },
    { key: 'resource_type', header: 'Kaynak', render: (row) => <Badge variant="outline">{row.resource_type || '-'} </Badge> },
    { key: 'created_at', header: 'Zaman', render: (row) => <span className="text-xs text-muted-foreground">{row.created_at}</span> },
  ]

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Audit Logs"
          description="Hassas aksiyonlar için denetim kayıtları."
        />

        <FilterBar
          searchPlaceholder="Aksiyon ara..."
          onSearchChange={(value) => setActionFilter(value || undefined)}
          actions={(
            <Button variant="outline" size="sm">
              <Filter className="h-4 w-4 mr-2" />
              Filtre
            </Button>
          )}
        />

        <DataTable
          columns={columns}
          data={logs || []}
          loading={isLoading}
          emptyState={(
            <EmptyState
              icon={<ListChecks className="h-6 w-6 text-primary" />}
              title="Kayıt yok"
              description="Henüz audit log kaydı bulunmuyor."
            />
          )}
        />
      </div>
    </ContentContainer>
  )
}
