'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Loader2, Mail, Lock, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/Logo'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, meApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { clearAdminTenantContext } from '@/lib/admin-tenant-context'

export default function LoginPageClient() {
  const router = useRouter()
  const { setUser, setTenant, setRole, setPermissions, setEntitlements, setFeatureFlags } = useAuthStore()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [twoFactorRequired, setTwoFactorRequired] = useState(false)
  const [twoFactorCode, setTwoFactorCode] = useState('')
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      // Never carry super-admin tenant context into user portal sessions.
      clearAdminTenantContext()
      const loginResponse = await authApi.login({
        ...formData,
        portal: 'tenant',
        two_factor_code: twoFactorRequired ? twoFactorCode : undefined,
      })
      const { access_token, refresh_token } = loginResponse.data

      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)

      const contextResponse = await meApi.getContext()
      const { user, tenant, role, permissions, entitlements, feature_flags } = contextResponse.data
      setUser(user)
      setTenant(tenant)
      setRole(role)
      setPermissions(permissions || [])
      setEntitlements(entitlements || {})
      setFeatureFlags(feature_flags || {})

      if (!user?.is_admin) {
        clearAdminTenantContext()
      }

      setTwoFactorRequired(false)
      setTwoFactorCode('')
      router.push('/dashboard')
    } catch (err: any) {
      const detail = err.response?.data?.detail
      const detailCode = detail?.code
      const detailMessage = detail?.message || detail

      if (detailCode === 'TWO_FACTOR_REQUIRED') {
        setTwoFactorRequired(true)
        setError(detailMessage || 'İki faktörlü doğrulama kodu gerekli.')
      } else if (detailCode === 'TWO_FACTOR_INVALID') {
        setTwoFactorRequired(true)
        setError(detailMessage || 'Doğrulama kodu geçersiz.')
      } else {
        setError(detailMessage || 'Giriş başarısız. Lütfen bilgilerinizi kontrol edin.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md animate-slide-up">
          {/* Logo */}
          <Link href="/" className="inline-flex items-center gap-3 mb-12">
            <Logo size="lg" showText={true} animated={true} />
          </Link>

          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2 gradient-text-vivid">Tekrar hoş geldiniz</h1>
            <p className="text-muted-foreground">
              Hesabınıza giriş yaparak devam edin
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="p-4 rounded-2xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm flex items-center gap-2 animate-shake">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium">E-posta</Label>
              <div className="relative input-glow rounded-xl transition-all duration-300">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="ornek@email.com"
                  className="pl-12 h-12 rounded-xl"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm font-medium">Şifre</Label>
                <Link href="/forgot-password" className="text-sm text-primary hover:underline">
                  Şifremi unuttum
                </Link>
              </div>
              <div className="flex items-center justify-end">
                <Link href="/register" className="text-xs text-muted-foreground hover:underline">
                  E-postanı doğrulamadın mı? Kayıt ekranından kod gir
                </Link>
              </div>
              <div className="relative input-glow rounded-xl transition-all duration-300">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  className="pl-12 h-12 rounded-xl"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                />
              </div>
            </div>

            {twoFactorRequired && (
              <div className="space-y-2">
                <Label htmlFor="two_factor_code" className="text-sm font-medium">Doğrulama Kodu</Label>
                <Input
                  id="two_factor_code"
                  type="text"
                  placeholder="Authenticator 6 haneli kod"
                  className="h-12 rounded-xl text-center tracking-[0.3em] text-lg"
                  value={twoFactorCode}
                  onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  required={twoFactorRequired}
                  minLength={6}
                  maxLength={6}
                />
              </div>
            )}

            <Button
              type="submit"
              className="w-full h-12 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-base font-medium shadow-lg shadow-blue-500/25 btn-shimmer"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Giriş yapılıyor...
                </>
              ) : (
                <>
                  Giriş Yap
                  <ArrowRight className="ml-2 w-5 h-5" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-8 text-center">
            <span className="text-muted-foreground">Hesabınız yok mu? </span>
            <Link href="/register" className="text-primary hover:underline font-medium">
              Ücretsiz kayıt olun
            </Link>
          </div>
        </div>
      </div>

      {/* Right Panel - Visual */}
      <div className="hidden lg:flex flex-1 relative bg-gradient-to-br from-blue-600 via-violet-600 to-purple-600 overflow-hidden">
        {/* Pattern */}
        <div className="absolute inset-0 dot-pattern opacity-20" />

        {/* Floating Elements */}
        <div className="absolute top-20 left-20 w-64 h-64 bg-white/10 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }} />
      </div>
    </div>
  )
}
