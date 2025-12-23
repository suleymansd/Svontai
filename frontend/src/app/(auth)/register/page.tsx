'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Loader2, Mail, Lock, User, Building2, ArrowRight, Check, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/Logo'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, tenantApi, userApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

export default function RegisterPage() {
  const router = useRouter()
  const { setUser, setTenant } = useAuthStore()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    password: '',
    company_name: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      await authApi.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
      })

      const loginResponse = await authApi.login({
        email: formData.email,
        password: formData.password,
      })
      
      const { access_token, refresh_token } = loginResponse.data
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)

      const userResponse = await userApi.getMe()
      setUser(userResponse.data)

      const tenantResponse = await tenantApi.createTenant({
        name: formData.company_name || formData.full_name + "'in İşletmesi",
      })
      setTenant(tenantResponse.data)

      router.push('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Kayıt başarısız. Lütfen tekrar deneyin.')
    } finally {
      setIsLoading(false)
    }
  }

  const benefits = [
    '14 gün ücretsiz deneme',
    'Kredi kartı gerekmez',
    'Dakikalar içinde başlayın',
    'İstediğiniz zaman iptal edin',
  ]

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Visual */}
      <div className="hidden lg:flex flex-1 relative bg-gradient-to-br from-violet-600 via-purple-600 to-blue-600 overflow-hidden">
        {/* Pattern */}
        <div className="absolute inset-0 dot-pattern opacity-20" />
        
        {/* Floating Elements */}
        <div className="absolute top-20 right-20 w-64 h-64 bg-white/10 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-20 left-20 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }} />
        
        {/* Content */}
        <div className="relative z-10 flex flex-col items-center justify-center p-16 text-white">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm mb-8">
            <Sparkles className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-medium">Ücretsiz Başlayın</span>
          </div>
          
          <h2 className="text-4xl font-bold text-center mb-6 max-w-lg">
            İşletmenizi 7/24 açık tutun
          </h2>
          
          <p className="text-lg text-purple-100 text-center max-w-md mb-12">
            Yapay zeka destekli asistanınız müşterilerinize anında yanıt versin.
          </p>

          {/* Benefits */}
          <div className="space-y-4">
            {benefits.map((benefit, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center">
                  <Check className="w-4 h-4" />
                </div>
                <span>{benefit}</span>
              </div>
            ))}
          </div>

          {/* Testimonial */}
          <div className="mt-16 p-6 rounded-2xl bg-white/10 backdrop-blur-sm max-w-md">
            <p className="text-purple-100 mb-4">
              "SvontAi sayesinde müşteri sorularına anında yanıt veriyoruz. 
              Satışlarımız %40 arttı!"
            </p>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500" />
              <div>
                <div className="font-medium">Ahmet Yılmaz</div>
                <div className="text-sm text-purple-200">E-ticaret İşletmesi</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Logo */}
          <Link href="/" className="inline-flex items-center gap-3 mb-12">
            <Logo size="lg" showText={true} animated={true} />
          </Link>

          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Hesap oluşturun</h1>
            <p className="text-muted-foreground">
              14 günlük ücretsiz deneme ile başlayın
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="p-4 rounded-2xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                {error}
              </div>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="full_name" className="text-sm font-medium">Ad Soyad</Label>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="full_name"
                  type="text"
                  placeholder="Adınız Soyadınız"
                  className="pl-12 h-12 rounded-xl"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="company_name" className="text-sm font-medium">İşletme Adı</Label>
              <div className="relative">
                <Building2 className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="company_name"
                  type="text"
                  placeholder="İşletmenizin adı"
                  className="pl-12 h-12 rounded-xl"
                  value={formData.company_name}
                  onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium">E-posta</Label>
              <div className="relative">
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
              <Label htmlFor="password" className="text-sm font-medium">Şifre</Label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  placeholder="En az 8 karakter"
                  className="pl-12 h-12 rounded-xl"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                  minLength={8}
                />
              </div>
            </div>

            <Button 
              type="submit" 
              className="w-full h-12 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-base font-medium shadow-lg shadow-blue-500/25" 
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Hesap oluşturuluyor...
                </>
              ) : (
                <>
                  Ücretsiz Başla
                  <ArrowRight className="ml-2 w-5 h-5" />
                </>
              )}
            </Button>

            <p className="text-xs text-muted-foreground text-center">
              Kayıt olarak{' '}
              <Link href="/terms" className="text-primary hover:underline">Kullanım Koşulları</Link>
              {' '}ve{' '}
              <Link href="/privacy" className="text-primary hover:underline">Gizlilik Politikası</Link>
              'nı kabul etmiş olursunuz.
            </p>
          </form>

          <div className="mt-8 text-center">
            <span className="text-muted-foreground">Zaten hesabınız var mı? </span>
            <Link href="/login" className="text-primary hover:underline font-medium">
              Giriş yapın
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
