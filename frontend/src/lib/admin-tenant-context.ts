export const ADMIN_TENANT_CONTEXT_ID_KEY = 'svontai_admin_tenant_context_id'
export const ADMIN_TENANT_CONTEXT_NAME_KEY = 'svontai_admin_tenant_context_name'

export type AdminTenantContext = {
  id: string
  name?: string
}

export function getAdminTenantContext(): AdminTenantContext | null {
  if (typeof window === 'undefined') {
    return null
  }

  const id = localStorage.getItem(ADMIN_TENANT_CONTEXT_ID_KEY)
  if (!id) {
    return null
  }

  const name = localStorage.getItem(ADMIN_TENANT_CONTEXT_NAME_KEY) || undefined
  return { id, name }
}

export function setAdminTenantContext(id: string, name?: string): void {
  if (typeof window === 'undefined') {
    return
  }

  localStorage.setItem(ADMIN_TENANT_CONTEXT_ID_KEY, id)
  if (name) {
    localStorage.setItem(ADMIN_TENANT_CONTEXT_NAME_KEY, name)
  } else {
    localStorage.removeItem(ADMIN_TENANT_CONTEXT_NAME_KEY)
  }
}

export function clearAdminTenantContext(): void {
  if (typeof window === 'undefined') {
    return
  }

  localStorage.removeItem(ADMIN_TENANT_CONTEXT_ID_KEY)
  localStorage.removeItem(ADMIN_TENANT_CONTEXT_NAME_KEY)
}
