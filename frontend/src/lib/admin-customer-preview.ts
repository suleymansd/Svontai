import type { QueryClient } from '@tanstack/react-query'
import { adminApi, meApi } from './api'
import {
  clearAdminTenantContext,
  getAdminTenantContext,
  setAdminTenantContext,
} from './admin-tenant-context'

type OpenCustomerPreviewOptions = {
  tenantId: string
  tenantName?: string
  queryClient: QueryClient
}

export async function openAdminCustomerPreview({
  tenantId,
  tenantName,
  queryClient,
}: OpenCustomerPreviewOptions): Promise<void> {
  const previousContext = getAdminTenantContext()

  await adminApi.startTenantPreview(tenantId)
  setAdminTenantContext(tenantId, tenantName)

  try {
    const response = await meApi.getContext()
    if (String(response.data?.tenant?.id || '') !== tenantId) {
      throw new Error('Müşteri oturumu doğrulanamadı')
    }

    await queryClient.cancelQueries()
    queryClient.clear()
    window.location.assign('/dashboard')
  } catch (error) {
    if (previousContext?.id) {
      setAdminTenantContext(previousContext.id, previousContext.name)
    } else {
      clearAdminTenantContext()
    }
    throw error
  }
}

export async function closeAdminCustomerPreview(queryClient: QueryClient): Promise<void> {
  clearAdminTenantContext()
  await queryClient.cancelQueries()
  queryClient.clear()
  window.location.assign('/admin')
}
