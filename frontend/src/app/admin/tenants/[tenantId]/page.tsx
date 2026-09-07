'use client'

import { useParams } from 'next/navigation'
import { TenantDetailView } from '@/components/admin/tenant-detail-view'

export default function TenantDetailPage() {
  const params = useParams<{ tenantId: string }>()
  return <TenantDetailView tenantId={params.tenantId} />
}
