'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, CheckCircle2, Loader2, Mail, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Logo } from '@/components/Logo'
import { authApi } from '@/lib/api'

type Step = 'request' | 'confirm' | 'done'

export default function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>('request')
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')

  const requestCode = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const response = await authApi.requestPasswordReset(email)
      setInfoMessage(response.data?.message || 'Doğrulama kodu gönderildi.')
      setStep('confirm')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Kod gönderimi sırasında hata oluştu.')
    } finally {
      setLoading(false)
    }
  }

  const confirmReset = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.confirmPasswordReset({
        email,
        code,
        new_password: password,
      })
      setStep('done')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Şifre güncellenemedi.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-2xl border border-border/70 bg-card p-6 shadow-soft">
        <Link href="/login" className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Girişe dön
        </Link>

        <div className="mb-8 flex items-center gap-3">
          <Logo size="md" showText={true} animated={false} />
        </div>

        {step !== 'done' && (
          <div className="mb-6">
            <h1 className="text-2xl font-semibold gradient-text-vivid">Şifre Sıfırlama</h1>
            <p className="text-sm text-muted-foreground mt-1">
              E-posta doğrulama kodu ile güvenli şifre güncelleyin.
            </p>
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-xl border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-600 dark:border-red-900 dark:bg-red-900/20 dark:text-red-300">
            {error}
          </div>
        )}
        {infoMessage && (
          <div className="mb-4 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
            {infoMessage}
          </div>
        )}

        {step === 'request' && (
          <form onSubmit={requestCode} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">E-posta adresi</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  className="pl-10"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="ornek@email.com"
                  required
                />
              </div>
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Kod Gönder
            </Button>
          </form>
        )}

        {step === 'confirm' && (
          <form onSubmit={confirmReset} className="space-y-4">
            <div className="rounded-xl border border-border/70 bg-muted/30 p-3 text-sm text-muted-foreground">
              <div className="flex items-center gap-2 font-medium text-foreground">
                <ShieldCheck className="h-4 w-4 text-primary" />
                Doğrulama kodu gönderildi
              </div>
              <p className="mt-1">{email}</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="code">Doğrulama kodu</Label>
              <Input
                id="code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="6 haneli kod"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Yeni şifre</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={8}
                placeholder="En az 8 karakter"
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Şifreyi Güncelle
            </Button>
          </form>
        )}

        {step === 'done' && (
          <div className="space-y-4 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-500">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <h2 className="text-xl font-semibold">Şifreniz güncellendi</h2>
            <p className="text-sm text-muted-foreground">
              Yeni şifreniz ile giriş yapabilirsiniz.
            </p>
            <Link href="/login">
              <Button className="w-full">Giriş Sayfasına Git</Button>
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
