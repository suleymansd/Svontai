'use client'

import { useParams } from 'next/navigation'
import { TenantDetailView } from '@/components/admin/tenant-detail-view'

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>()
  return <TenantDetailView tenantId={params.id} />
}
