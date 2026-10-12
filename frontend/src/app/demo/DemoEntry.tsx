'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Mail, RotateCw } from 'lucide-react'
import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { demoAccessApi } from '@/lib/demo-access'
import { meApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { getRefreshPromise, setAccessToken } from '@/lib/auth-token'
import { useAuthStore, useToolStore } from '@/lib/store'

export default function DemoEntry() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const started = useRef(false)
  const token = useRef('')
  const [error, setError] = useState('')
  const [retryable, setRetryable] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (started.current) return
    started.current = true
    token.current ||= new URLSearchParams(window.location.hash.slice(1)).get('token') || ''
    // Remove the credential before navigation, analytics or any outgoing links.
    window.history.replaceState(null, '', '/demo')
    if (!/^[A-Za-z0-9_-]{43}$/.test(token.current)) {
      setError('Erişim bağlantısı eksik. E-postanızdaki özel bağlantıyı yeniden açın.')
      return
    }
    const enter = async () => {
      try {
        setError('')
        await getRefreshPromise()?.catch(() => undefined)
        const response = await demoAccessApi.enter(token.current)
        await queryClient.cancelQueries()
        queryClient.clear()
        useAuthStore.getState().logout()
        useToolStore.getState().resetTools()
        setAccessToken(response.data.access_token)
        const { data } = await meApi.getContext()
        const store = useAuthStore.getState()
        store.setUser(data.user)
        store.setTenant(data.tenant)
        store.setRole(data.role)
        store.setPermissions(data.permissions || [])
        store.setEntitlements(data.entitlements || {})
        store.setFeatureFlags(data.feature_flags || {})
        store.setSessionReady(true)
        token.current = ''
        router.replace('/dashboard')
      } catch (cause: any) {
        setRetryable(!cause.response || cause.response.status >= 500 || cause.response.status === 429)
        setError(getApiErrorMessage(cause, 'Panel açılamadı. Lütfen yeniden deneyin.'))
      }
    }
    void enter()
  }, [attempt, queryClient, router])

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <div className="w-full max-w-md text-center">
        <div className="mb-10 flex justify-center"><Logo size="lg" /></div>
        {error ? (
          <>
            <h1 className="text-2xl font-semibold">Erişim tamamlanamadı</h1>
            <p role="alert" className="mt-4 text-sm leading-6 text-muted-foreground">{error}</p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              {retryable && <Button onClick={() => { started.current = false; setAttempt(value => value + 1) }}><RotateCw className="mr-2 h-4 w-4" />Tekrar dene</Button>}
              <Button variant="outline" asChild><a href="mailto:info@svontai.com"><Mail className="mr-2 h-4 w-4" />İletişime geç</a></Button>
            </div>
          </>
        ) : (
          <div role="status" aria-live="polite">
            <Loader2 className="mx-auto mb-6 h-7 w-7 animate-spin text-primary motion-reduce:animate-none" />
            <h1 className="text-2xl font-semibold">Premium paneliniz açılıyor</h1>
          </div>
        )}
        <div className="mt-12 flex justify-center gap-5 text-xs text-muted-foreground">
          <Link href="/privacy">Gizlilik</Link><Link href="/terms">Kullanım şartları</Link>
        </div>
      </div>
    </main>
  )
}
