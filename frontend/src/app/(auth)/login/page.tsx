'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2, Mail, Lock, ArrowRight, Sparkles, ShieldCheck, UserCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/Logo'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, meApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { clearAdminTenantContext, getAdminTenantContext } from '@/lib/admin-tenant-context'

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { setUser, setTenant, setRole, setPermissions, setEntitlements, setFeatureFlags } = useAuthStore()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [twoFactorRequired, setTwoFactorRequired] = useState(false)
  const [twoFactorCode, setTwoFactorCode] = useState('')
  const [portalMode, setPortalMode] = useState<'tenant' | 'super_admin'>(
    searchParams.get('portal') === 'super_admin' ? 'super_admin' : 'tenant'
  )
  const [adminSessionNote, setAdminSessionNote] = useState('')
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      if (portalMode === 'super_admin') {
        clearAdminTenantContext()
      }
      const loginResponse = await authApi.login({
        ...formData,
        portal: portalMode,
        admin_session_note: portalMode === 'super_admin' ? adminSessionNote.trim() : undefined,
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
      const adminTenantContext = getAdminTenantContext()
      if (user?.is_admin) {
        router.push(portalMode === 'super_admin' || !adminTenantContext?.id ? '/admin' : '/dashboard')
      } else {
        router.push('/dashboard')
      }
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
      } else if (detailCode === 'ADMIN_PORTAL_FORBIDDEN') {
        setError(detailMessage || 'Bu hesap süper admin paneline erişemez.')
      } else if (detailCode === 'ADMIN_SESSION_NOTE_REQUIRED') {
        setError(detailMessage || 'Süper admin giriş notu zorunlu.')
      } else if (detailCode === 'SUPER_ADMIN_2FA_SETUP_REQUIRED') {
        setError(detailMessage || 'Süper admin için 2FA etkinleştirilmeli.')
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
            <div className="rounded-2xl border border-border/70 bg-card/60 p-2">
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setPortalMode('tenant')}
                  className={`inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${portalMode === 'tenant' ? 'bg-primary text-primary-foreground' : 'bg-transparent text-muted-foreground hover:bg-muted/60'}`}
                >
                  <UserCircle2 className="h-4 w-4" />
                  Kullanıcı Paneli
                </button>
                <button
                  type="button"
                  onClick={() => setPortalMode('super_admin')}
                  className={`inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${portalMode === 'super_admin' ? 'bg-primary text-primary-foreground' : 'bg-transparent text-muted-foreground hover:bg-muted/60'}`}
                >
                  <ShieldCheck className="h-4 w-4" />
                  Super Admin
                </button>
              </div>
            </div>

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

            {portalMode === 'super_admin' && (
              <div className="space-y-2">
                <Label htmlFor="admin_session_note" className="text-sm font-medium">Oturum Notu</Label>
                <Input
                  id="admin_session_note"
                  type="text"
                  placeholder="Örn: Tenant denetimi / destek müdahalesi"
                  className="h-12 rounded-xl"
                  value={adminSessionNote}
                  onChange={(e) => setAdminSessionNote(e.target.value)}
                  required={portalMode === 'super_admin'}
                  minLength={8}
                />
                <p className="text-xs text-muted-foreground">
                  Güvenlik audit kaydı için bu alan zorunludur.
                </p>
              </div>
            )}

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
                  {portalMode === 'super_admin' ? 'Super Admin Girişi' : 'Giriş Yap'}
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

        {/* Content */}
        <div className="relative z-10 flex flex-col items-center justify-center p-16 text-white">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm mb-8">
            <Sparkles className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-medium">AI-Powered Customer Support</span>
          </div>

          <h2 className="text-4xl font-bold text-center mb-6 max-w-lg">
            Müşteri desteğinizi yapay zeka ile güçlendirin
          </h2>

          <p className="text-lg text-blue-100 text-center max-w-md">
            7/24 kesintisiz hizmet, anında yanıtlar ve mutlu müşteriler.
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-8 mt-12">
            {[
              { value: '10K+', label: 'Kullanıcı' },
              { value: '5M+', label: 'Mesaj' },
              { value: '%99', label: 'Memnuniyet' },
            ].map((stat, i) => (
              <div key={i} className="text-center animate-scale-in" style={{ animationDelay: `${i * 200}ms` }}>
                <div className="text-3xl font-bold">{stat.value}</div>
                <div className="text-sm text-blue-200">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
