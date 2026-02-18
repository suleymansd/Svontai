'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowRight, Loader2, Lock, Mail, ShieldCheck } from 'lucide-react'

import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, meApi } from '@/lib/api'
import { clearAdminTenantContext } from '@/lib/admin-tenant-context'
import { useAuthStore } from '@/lib/store'

export default function AdminLoginPageClient() {
  const router = useRouter()
  const { setUser, setTenant, setRole, setPermissions, setEntitlements, setFeatureFlags } = useAuthStore()

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [twoFactorRequired, setTwoFactorRequired] = useState(false)
  const [twoFactorCode, setTwoFactorCode] = useState('')
  const [adminSessionNote, setAdminSessionNote] = useState('')
  const [formData, setFormData] = useState({ email: '', password: '' })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      clearAdminTenantContext()

      const loginResponse = await authApi.login({
        ...formData,
        portal: 'super_admin',
        admin_session_note: adminSessionNote.trim(),
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

      setTwoFactorRequired(false)
      setTwoFactorCode('')

      router.push('/admin')
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
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md animate-slide-up">
          <Link href="/" className="inline-flex items-center gap-3 mb-12">
            <Logo size="lg" showText={true} animated={true} />
          </Link>

          <div className="mb-8">
            <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 text-primary px-3 py-1 text-xs font-medium mb-4">
              <ShieldCheck className="h-4 w-4" />
              Super Admin Portal
            </div>
            <h1 className="text-3xl font-bold mb-2 gradient-text-vivid">Yönetim girişi</h1>
            <p className="text-muted-foreground">SvontAI şirket yönetim paneline giriş yapın</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="p-4 rounded-2xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm flex items-center gap-2 animate-shake">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium">
                E-posta
              </Label>
              <div className="relative input-glow rounded-xl transition-all duration-300">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="admin@svontai.com"
                  className="pl-12 h-12 rounded-xl"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">
                Şifre
              </Label>
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

            <div className="space-y-2">
              <Label htmlFor="admin_session_note" className="text-sm font-medium">
                Oturum Notu
              </Label>
              <Input
                id="admin_session_note"
                type="text"
                placeholder="Örn: Tenant denetimi / destek müdahalesi"
                className="h-12 rounded-xl"
                value={adminSessionNote}
                onChange={(e) => setAdminSessionNote(e.target.value)}
                required
                minLength={8}
              />
              <p className="text-xs text-muted-foreground">Güvenlik audit kaydı için zorunludur.</p>
            </div>

            {twoFactorRequired && (
              <div className="space-y-2">
                <Label htmlFor="two_factor_code" className="text-sm font-medium">
                  Doğrulama Kodu
                </Label>
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
              className="w-full h-12 rounded-xl bg-gradient-to-r from-slate-900 to-slate-700 hover:from-slate-950 hover:to-slate-800 text-base font-medium shadow-lg shadow-slate-900/25 btn-shimmer"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Giriş yapılıyor...
                </>
              ) : (
                <>
                  Super Admin Girişi
                  <ArrowRight className="ml-2 w-5 h-5" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-8 text-center">
            <Link href="/login" className="text-xs text-muted-foreground hover:underline">
              Kullanıcı paneline dön
            </Link>
          </div>
        </div>
      </div>

      <div className="hidden lg:flex flex-1 relative bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 overflow-hidden">
        <div className="absolute inset-0 dot-pattern opacity-20" />
        <div className="absolute top-24 left-24 w-72 h-72 bg-white/10 rounded-full blur-3xl animate-float" />
        <div
          className="absolute bottom-24 right-24 w-[34rem] h-[34rem] bg-slate-500/10 rounded-full blur-3xl animate-float"
          style={{ animationDelay: '2s' }}
        />
      </div>
    </div>
  )
}

