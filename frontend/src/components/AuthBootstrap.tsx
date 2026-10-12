"use client"

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { RefreshCw, WifiOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { meApi, refreshAccessToken } from '@/lib/api'
import { getAccessToken } from '@/lib/auth-token'
import { useAuthStore } from '@/lib/store'

export function AuthBootstrap() {
  const pathname = usePathname()
  const isDemoEntry = pathname === '/demo'
  const isProtectedPage = pathname.startsWith('/dashboard') || pathname.startsWith('/panel') || (pathname.startsWith('/admin') && pathname !== '/admin/login')
  const [sessionError, setSessionError] = useState(false)
  const [attempt, setAttempt] = useState(0)
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
    // The demo route performs its own exchange; do not race a previous session.
    if (isDemoEntry) return
    let cancelled = false

    const loadContext = async () => {
      let finished = true
      setSessionError(false)
      if (isProtectedPage) setSessionReady(false)
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
      } catch (error) {
        if (cancelled) return
        const status = (error as { response?: { status?: number } }).response?.status
        if (status === 401 || status === 403) {
          logout()
        } else if (isProtectedPage) {
          finished = false
          setSessionError(true)
        }
      } finally {
        if (!cancelled && finished) setSessionReady(true)
      }
    }

    void loadContext()
    return () => {
      cancelled = true
    }
  }, [isDemoEntry, isProtectedPage, attempt, setUser, setTenant, setRole, setPermissions, setEntitlements, setFeatureFlags, setSessionReady, logout])

  if (!sessionError || !isProtectedPage) return null
  return (
    <section role="alert" className="fixed inset-0 z-[100] flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
      <WifiOff aria-hidden="true" className="h-8 w-8 text-muted-foreground" />
      <h1 className="text-xl font-semibold">Bağlantı kurulamadı</h1>
      <p className="max-w-md text-sm text-muted-foreground">Oturumunuz korunuyor. Bağlantı sağlandığında tekrar deneyebilirsiniz.</p>
      <Button onClick={() => setAttempt((value) => value + 1)}>
        <RefreshCw aria-hidden="true" className="mr-2 h-4 w-4" />Yeniden Dene
      </Button>
    </section>
  )
}
