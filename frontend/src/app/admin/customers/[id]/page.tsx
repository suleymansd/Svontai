'use client'

import { useParams } from 'next/navigation'
import { TenantDetailView } from '../../tenants/[tenantId]/page'

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>()
  return <TenantDetailView tenantId={params.id} />
}
