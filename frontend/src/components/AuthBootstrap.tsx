"use client"

import { useEffect } from 'react'
import { meApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

export function AuthBootstrap() {
  const {
    setUser,
    setTenant,
    setRole,
    setPermissions,
    setEntitlements,
    setFeatureFlags,
  } = useAuthStore()

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      return
    }

    const loadContext = async () => {
      try {
        const response = await meApi.getContext()
        const { user, tenant, role, permissions, entitlements, feature_flags } = response.data
        setUser(user)
        setTenant(tenant)
        setRole(role)
        setPermissions(permissions || [])
        setEntitlements(entitlements || {})
        setFeatureFlags(feature_flags || {})
      } catch {
        // Token invalid; allow existing logout flow elsewhere.
      }
    }

    loadContext()
  }, [setUser, setTenant, setRole, setPermissions, setEntitlements, setFeatureFlags])

  return null
}
