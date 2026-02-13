"use client"

import { useAuthStore } from '@/lib/store'
import { hasAnyPermission } from '@/lib/permissions'

export function PermissionGate({
  permissions,
  children,
  fallback = null,
}: {
  permissions: string[]
  children: React.ReactNode
  fallback?: React.ReactNode
}) {
  const userPermissions = useAuthStore((state) => state.permissions)
  if (!hasAnyPermission(userPermissions, permissions)) {
    return <>{fallback}</>
  }

  return <>{children}</>
}
