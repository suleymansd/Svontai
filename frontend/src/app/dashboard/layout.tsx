'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import { 
  LayoutDashboard, 
  Bot, 
  MessagesSquare, 
  Users, 
  Settings,
  LogOut,
  Menu,
  X,
  ChevronRight,
  Bell,
  Search,
  Sparkles,
  Smartphone,
  BarChart3,
  CreditCard,
  Headphones,
  Rocket
} from 'lucide-react'
import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useAuthStore, useUIStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import { useQuery } from '@tanstack/react-query'
import { setupOnboardingApi, subscriptionApi } from '@/lib/api'

const sidebarItems = [
  { name: 'Genel Bakış', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Botlarım', href: '/dashboard/bots', icon: Bot },
  { name: 'Konuşmalar', href: '/dashboard/conversations', icon: MessagesSquare },
  { name: 'Leadler', href: '/dashboard/leads', icon: Users },
  { name: 'Analitikler', href: '/dashboard/analytics', icon: BarChart3 },
  { name: 'Operatör', href: '/dashboard/operator', icon: Headphones, feature: 'operator_takeover' },
]

const secondaryItems = [
  { name: 'WhatsApp Kurulum', href: '/dashboard/setup/whatsapp', icon: Smartphone },
  { name: 'Abonelik', href: '/dashboard/billing', icon: CreditCard },
  { name: 'Ayarlar', href: '/dashboard/settings', icon: Settings },
]

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const pathname = usePathname()
  const { user, tenant, isAuthenticated, logout } = useAuthStore()
  const { sidebarOpen, setSidebarOpen, toggleSidebar } = useUIStore()
  const [mounted, setMounted] = useState(false)

  // Fetch onboarding status
  const { data: onboardingStatus } = useQuery({
    queryKey: ['onboarding-status'],
    queryFn: () => setupOnboardingApi.getStatus().then(res => res.data),
    enabled: isAuthenticated,
  })

  // Fetch subscription for features
  const { data: usageStats } = useQuery({
    queryKey: ['usage-stats'],
    queryFn: () => subscriptionApi.getUsageStats().then(res => res.data),
    enabled: isAuthenticated,
  })

  useEffect(() => {
    setMounted(true)
    if (!isAuthenticated) {
      router.push('/login')
    }
  }, [isAuthenticated, router])

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  if (!mounted || !isAuthenticated) {
    return null
  }

  const showOnboardingBanner = onboardingStatus && !onboardingStatus.is_completed && !onboardingStatus.dismissed

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={cn(
        'fixed top-0 left-0 z-50 h-full w-72 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 transition-transform duration-300 lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-6 border-b border-slate-200 dark:border-slate-800">
            <Link href="/dashboard" className="flex items-center">
              <Logo size="md" showText={true} animated={true} />
            </Link>
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(false)}>
              <X className="w-5 h-5" />
            </Button>
          </div>

          {/* Tenant Selector */}
          <div className="px-4 py-4">
            <div className="p-3 rounded-xl bg-gradient-to-r from-blue-50 to-violet-50 dark:from-blue-900/20 dark:to-violet-900/20 border border-blue-100 dark:border-blue-800/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white font-semibold">
                  {tenant?.name?.charAt(0).toUpperCase() || 'İ'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{tenant?.name || 'Yükleniyor...'}</p>
                  <p className="text-xs text-muted-foreground">
                    {usageStats?.plan_name || 'Yükleniyor...'}
                  </p>
                </div>
                <ChevronRight className="w-4 h-4 text-muted-foreground" />
              </div>
            </div>
          </div>

          {/* Onboarding Banner */}
          {showOnboardingBanner && (
            <div className="px-4 mb-2">
              <Link href="/dashboard/onboarding">
                <div className="p-3 rounded-xl bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border border-amber-200 dark:border-amber-800/50 cursor-pointer hover:shadow-md transition-shadow">
                  <div className="flex items-center gap-2">
                    <Rocket className="w-5 h-5 text-amber-600" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-amber-900 dark:text-amber-100">Kurulumu Tamamla</p>
                      <p className="text-xs text-amber-700 dark:text-amber-200">%{onboardingStatus?.progress_percentage} tamamlandı</p>
                    </div>
                  </div>
                  <div className="mt-2 w-full h-1.5 bg-amber-200 dark:bg-amber-800 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-amber-500"
                      style={{ width: `${onboardingStatus?.progress_percentage}%` }}
                    />
                  </div>
                </div>
              </Link>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
            <p className="px-3 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Ana Menü
            </p>
            {sidebarItems.map((item) => {
              // Check if feature is enabled
              if (item.feature && usageStats?.features && !usageStats.features[item.feature]) {
                return null
              }
              
              const isActive = pathname === item.href || 
                (item.href !== '/dashboard' && pathname.startsWith(item.href))
              
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                    isActive 
                      ? 'bg-gradient-to-r from-blue-500 to-violet-600 text-white shadow-lg shadow-blue-500/25' 
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                  )}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.name}</span>
                </Link>
              )
            })}

            <p className="px-3 py-2 mt-4 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Yönetim
            </p>
            {secondaryItems.map((item) => {
              const isActive = pathname === item.href || 
                (item.href !== '/dashboard' && pathname.startsWith(item.href))
              
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                    isActive 
                      ? 'bg-gradient-to-r from-blue-500 to-violet-600 text-white shadow-lg shadow-blue-500/25' 
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                  )}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.name}</span>
                </Link>
              )
            })}
          </nav>

          {/* Upgrade Card */}
          {usageStats?.plan_type === 'free' && (
            <div className="p-4">
              <div className="p-4 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 text-white">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-5 h-5" />
                  <span className="font-semibold">Pro'ya Yükseltin</span>
                </div>
                <p className="text-sm text-violet-100 mb-3">
                  Sınırsız bot ve mesaj ile işletmenizi büyütün.
                </p>
                <Link href="/dashboard/billing">
                  <Button size="sm" className="w-full bg-white text-violet-600 hover:bg-violet-50">
                    Planları Gör
                  </Button>
                </Link>
              </div>
            </div>
          )}

          {/* Usage Stats */}
          {usageStats && (
            <div className="px-4 pb-2">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Mesaj Kullanımı</span>
                  <span className="font-medium">{usageStats.messages_used} / {usageStats.message_limit}</span>
                </div>
                <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className={cn(
                      'h-full transition-all',
                      usageStats.message_usage_percent > 80 ? 'bg-red-500' : 'bg-blue-500'
                    )}
                    style={{ width: `${usageStats.message_usage_percent}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* User info */}
          <div className="p-4 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white font-semibold">
                {user?.full_name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.full_name}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={handleLogout} className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20">
                <LogOut className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-72">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between h-16 px-4 lg:px-8 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={toggleSidebar}>
              <Menu className="w-5 h-5" />
            </Button>
            
            {/* Search */}
            <div className="hidden sm:flex relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input 
                placeholder="Ara..." 
                className="w-64 pl-9 h-9 rounded-lg bg-slate-100 dark:bg-slate-800 border-0"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Trial Badge */}
            {usageStats?.status === 'trial' && (
              <Badge variant="warning" className="hidden sm:flex">
                Deneme Sürümü
              </Badge>
            )}
            
            {/* Notifications */}
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
            </Button>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
