'use client'

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft, CheckCircle2, Loader2, Mail, MailCheck, RefreshCw } from 'lucide-react'

import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'

const RESEND_WAIT_SECONDS = 60

export default function VerifyEmailPageClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialEmail = searchParams.get('email') || ''
  const requestedNext = searchParams.get('next')
  const loginPath = requestedNext === '/admin/login' ? '/admin/login' : '/login'
  const autoRequestStarted = useRef(false)

  const [email, setEmail] = useState(initialEmail)
  const [code, setCode] = useState('')
  const [codeRequested, setCodeRequested] = useState(false)
  const [isRequesting, setIsRequesting] = useState(false)
  const [isConfirming, setIsConfirming] = useState(false)
  const [resendSeconds, setResendSeconds] = useState(0)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const requestCode = useCallback(async (targetEmail: string) => {
    const normalizedEmail = targetEmail.trim().toLowerCase()
    if (!normalizedEmail) {
      setError('E-posta adresinizi girin.')
      return
    }

    setIsRequesting(true)
    setError('')
    setMessage('')
    try {
      const response = await authApi.requestEmailVerification(normalizedEmail)
      if (response.data?.verified) {
        router.replace(`${loginPath}?verified=1&email=${encodeURIComponent(normalizedEmail)}`)
        return
      }
      setEmail(normalizedEmail)
      setCodeRequested(true)
      setResendSeconds(RESEND_WAIT_SECONDS)
      setMessage(response.data?.message || 'Doğrulama kodu e-posta adresinize gönderildi.')
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, 'Doğrulama kodu gönderilemedi. Lütfen tekrar deneyin.'))
    } finally {
      setIsRequesting(false)
    }
  }, [loginPath, router])

  useEffect(() => {
    if (!initialEmail || autoRequestStarted.current) return
    autoRequestStarted.current = true
    void requestCode(initialEmail)
  }, [initialEmail, requestCode])

  useEffect(() => {
    if (resendSeconds <= 0) return
    const timer = window.setInterval(() => {
      setResendSeconds((current) => Math.max(0, current - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [resendSeconds])

  const handleRequest = async (event: FormEvent) => {
    event.preventDefault()
    await requestCode(email)
  }

  const handleConfirm = async (event: FormEvent) => {
    event.preventDefault()
    if (code.length !== 6) {
      setError('6 haneli doğrulama kodunu girin.')
      return
    }

    setIsConfirming(true)
    setError('')
    setMessage('')
    try {
      await authApi.confirmEmailVerification({ email: email.trim().toLowerCase(), code })
      router.replace(`${loginPath}?verified=1&email=${encodeURIComponent(email.trim().toLowerCase())}`)
    } catch (confirmError: unknown) {
      setError(getApiErrorMessage(confirmError, 'Kod doğrulanamadı. Kodu kontrol edip tekrar deneyin.'))
    } finally {
      setIsConfirming(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-5 py-10">
      <div className="w-full max-w-md">
        <Link href="/" className="mb-10 inline-flex">
          <Logo size="lg" showText animated />
        </Link>

        <div className="mb-8">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-300">
            <MailCheck className="h-6 w-6" />
          </div>
          <h1 className="text-3xl font-bold">E-postanızı doğrulayın</h1>
          <p className="mt-2 text-muted-foreground">
            Hesabınızı kullanmaya devam etmek için e-posta adresinize gönderilen 6 haneli kodu girin.
          </p>
        </div>

        {error ? (
          <div className="mb-5 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
            {error}
          </div>
        ) : null}

        {message ? (
          <div className="mb-5 flex items-start gap-3 rounded-md border border-green-200 bg-green-50 p-4 text-sm text-green-700 dark:border-green-900 dark:bg-green-950/30 dark:text-green-300">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            {message}
          </div>
        ) : null}

        {!codeRequested ? (
          <form onSubmit={handleRequest} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="verification_email">E-posta</Label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="verification_email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="ornek@email.com"
                  className="h-12 pl-12"
                  required
                  autoFocus={!initialEmail}
                />
              </div>
            </div>
            <Button type="submit" className="h-12 w-full" disabled={isRequesting}>
              {isRequesting ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Mail className="mr-2 h-5 w-5" />}
              Kodu Gönder
            </Button>
          </form>
        ) : (
          <form onSubmit={handleConfirm} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="verification_code">Doğrulama kodu</Label>
              <Input
                id="verification_code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className="h-14 text-center text-xl tracking-[0.35em]"
                minLength={6}
                maxLength={6}
                required
                autoFocus
              />
              <p className="text-sm text-muted-foreground">{email} adresine gönderildi.</p>
            </div>

            <Button type="submit" className="h-12 w-full" disabled={isConfirming}>
              {isConfirming ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <MailCheck className="mr-2 h-5 w-5" />}
              E-postayı Doğrula
            </Button>

            <Button
              type="button"
              variant="outline"
              className="h-11 w-full"
              disabled={isRequesting || resendSeconds > 0}
              onClick={() => void requestCode(email)}
            >
              {isRequesting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              {resendSeconds > 0 ? `Tekrar gönder (${resendSeconds})` : 'Kodu Tekrar Gönder'}
            </Button>
          </form>
        )}

        <Link href={loginPath} className="mt-8 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Giriş ekranına dön
        </Link>
      </div>
    </main>
  )
}
