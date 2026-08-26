"use client"

import { useEffect } from 'react'
import { meApi, refreshAccessToken } from '@/lib/api'
import { getAccessToken } from '@/lib/auth-token'
import { useAuthStore } from '@/lib/store'

export function AuthBootstrap() {
  const {
    setUser,
    setTenant,
    setRole,
    setPermissions,
    setEntitlements,
    setFeatureFlags,
    setSessionReady,
    logout,
  } = useAuthStore()

  useEffect(() => {
    let cancelled = false

    const loadContext = async () => {
      try {
        if (!getAccessToken()) await refreshAccessToken()
        const response = await meApi.getContext()
        if (cancelled) return
        const { user, tenant, role, permissions, entitlements, feature_flags } = response.data
        setUser(user)
        setTenant(tenant)
        setRole(role)
        setPermissions(permissions || [])
        setEntitlements(entitlements || {})
        setFeatureFlags(feature_flags || {})
      } catch {
        if (!cancelled) logout()
      } finally {
        if (!cancelled) setSessionReady(true)
      }
    }

    void loadContext()
    return () => {
      cancelled = true
    }
  }, [setUser, setTenant, setRole, setPermissions, setEntitlements, setFeatureFlags, setSessionReady, logout])

  return null
}
