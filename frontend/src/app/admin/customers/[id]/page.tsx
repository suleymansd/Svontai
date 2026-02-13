'use client'

import TenantDetailPage from '../../tenants/[tenantId]/page'

export default function CustomerDetailPage({ params }: { params: { id: string } }) {
  return <TenantDetailPage params={{ tenantId: params.id }} />
}
