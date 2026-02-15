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
  LifeBuoy,
  Rocket,
  ChevronsUpDown,
  User,
  Plus,
  Gauge,
  Boxes
} from 'lucide-react'
import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useAuthStore, useToolStore, useUIStore } from '@/lib/store'
import { cn, maskEmail } from '@/lib/utils'
import { useQuery } from '@tanstack/react-query'
import { setupOnboardingApi, subscriptionApi } from '@/lib/api'
import { getToolMenuItems } from '@/components/tools/registry'
import { clearAdminTenantContext, getAdminTenantContext } from '@/lib/admin-tenant-context'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { ToolIcon3D } from '@/components/tools/ToolIcon3D'

const sidebarItems = [
  { name: 'Genel Bakış', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Tool Kataloğu', href: '/dashboard/tools', icon: Boxes },
  { name: 'Botlarım', href: '/dashboard/bots', icon: Bot },
  { name: 'Konuşmalar', href: '/dashboard/conversations', icon: MessagesSquare },
  { name: 'Leadler', href: '/dashboard/leads', icon: Users },
  { name: 'Analitikler', href: '/dashboard/analytics', icon: BarChart3 },
  { name: 'Operatör', href: '/dashboard/operator', icon: Headphones, feature: 'operator_takeover' },
  { name: 'Hata Merkezi', href: '/dashboard/errors', icon: Bell },
  { name: 'Destek', href: '/dashboard/tickets', icon: LifeBuoy },
]

const secondaryItems = [
  { name: 'WhatsApp Kurulum', href: '/dashboard/setup/whatsapp', icon: Smartphone },
  { name: 'Kullanım', href: '/dashboard/usage', icon: Gauge },
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
  const { installedToolIds, toolConfigs } = useToolStore()
  const { sidebarOpen, setSidebarOpen, toggleSidebar } = useUIStore()
  const [mounted, setMounted] = useState(false)
  const toolMenuItems = getToolMenuItems(installedToolIds, toolConfigs)

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
      return
    }

    if (user?.is_admin && !getAdminTenantContext()?.id) {
      router.push('/admin')
    }
  }, [isAuthenticated, user?.is_admin, router])

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  const handleExitAdminContext = () => {
    clearAdminTenantContext()
    router.push('/admin')
  }

  if (!mounted || !isAuthenticated) {
    return null
  }

  const showOnboardingBanner = onboardingStatus && !onboardingStatus.is_completed && !onboardingStatus.dismissed

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={cn(
        'fixed top-0 left-0 z-50 h-full w-72 bg-card/95 backdrop-blur-xl border-r border-border/70 transition-transform duration-300 lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-6 border-b border-border/70">
            <Link href="/dashboard" className="flex items-center">
              <Logo size="md" showText={true} animated={true} />
            </Link>
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(false)}>
              <X className="w-5 h-5" />
            </Button>
          </div>

          {/* Tenant Selector */}
          <div className="px-4 py-4">
            <div className="p-3 rounded-xl border border-border/70 glass-card">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 text-primary flex items-center justify-center font-semibold shadow-glow-primary">
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
                <div className="p-3 rounded-xl border border-warning/40 bg-warning-subtle/40 cursor-pointer hover:shadow-soft transition-shadow">
                  <div className="flex items-center gap-2">
                    <Rocket className="w-5 h-5 text-warning" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-warning">Kurulumu Tamamla</p>
                      <p className="text-xs text-muted-foreground">%{onboardingStatus?.progress_percentage} tamamlandı</p>
                    </div>
                  </div>
                  <div className="mt-2 w-full h-1.5 bg-warning/30 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-warning"
                      style={{ width: `${onboardingStatus?.progress_percentage}%` }}
                    />
                  </div>
                </div>
              </Link>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
            <p className="px-3 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">
              Ana Menü
            </p>
            {sidebarItems.map((item) => {
              // Check if feature is enabled
              if (item.feature) {
                const enabled = usageStats?.features?.[item.feature]
                if (enabled !== true) return null
              }

              const isActive = pathname === item.href ||
                (item.href !== '/dashboard' && pathname.startsWith(item.href))

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'nav-active-glow text-primary'
                      : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                  )}
                >
                  <Icon3DBadge
                    icon={item.icon}
                    size="sm"
                    active
                    from={isActive ? 'from-primary' : 'from-slate-200 dark:from-slate-800'}
                    to={isActive ? 'to-violet-500' : 'to-slate-50 dark:to-slate-700'}
                    className={cn(
                      'shadow-[0_10px_22px_rgba(0,0,0,0.18)] transition-transform duration-200 group-hover:-translate-y-0.5',
                      isActive && 'ring-2 ring-primary/25'
                    )}
                  />
                  <span>{item.name}</span>
                </Link>
              )
            })}

            <p className="px-3 py-2 mt-4 text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">
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
                      ? 'nav-active-glow text-primary'
                      : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                  )}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.name}</span>
                </Link>
              )
            })}

            {toolMenuItems.length > 0 && (
              <>
                <p className="px-3 py-2 mt-4 text-[11px] font-semibold text-muted-foreground uppercase tracking-widest">
                  Tool Sayfaları
                </p>
                {toolMenuItems.map((item) => {
                  const isActive = pathname === item.href || pathname.startsWith(item.href)
                  return (
                    <Link
                      key={item.id}
                      href={item.href}
                      className={cn(
                        'group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                        isActive
                          ? 'nav-active-glow text-primary'
                          : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                      )}
                    >
                      <ToolIcon3D
                        toolId={item.id}
                        size="sm"
                        active
                        className={cn(
                          'shadow-[0_10px_22px_rgba(0,0,0,0.18)] transition-transform duration-200 group-hover:-translate-y-0.5',
                          isActive && 'ring-2 ring-primary/25'
                        )}
                      />
                      <span>{item.name}</span>
                    </Link>
                  )
                })}
              </>
            )}
          </nav>

          {/* Upgrade Card */}
          {usageStats?.plan_type === 'free' && (
            <div className="p-4">
              <div className="rounded-2xl border border-border/70 bg-gradient-to-br from-primary/10 to-cyan-500/10 p-4 animate-gradient" style={{ backgroundSize: '200% 200%' }}>
                <div className="mb-2 flex items-center gap-2 text-primary">
                  <Sparkles className="w-5 h-5" />
                  <span className="font-semibold">Pro'ya Yükseltin</span>
                </div>
                <p className="mb-3 text-sm text-muted-foreground">
                  Sınırsız bot ve mesaj ile işletmenizi büyütün.
                </p>
                <Link href="/dashboard/billing">
                  <Button size="sm" className="w-full">
                    Planları Gör
                  </Button>
                </Link>
              </div>
            </div>
          )}

          {/* Usage Stats */}
          {usageStats && (
            <div className="px-4 pb-2">
              <div className="rounded-xl border border-border/70 glass-card p-3">
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Mesaj Kullanımı</span>
                  <span className="font-medium">{usageStats.messages_used} / {usageStats.message_limit}</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      'h-full transition-all duration-500',
                      usageStats.message_usage_percent > 80 ? 'bg-gradient-to-r from-destructive to-red-400' : 'bg-gradient-to-r from-primary to-cyan-400'
                    )}
                    style={{ width: `${usageStats.message_usage_percent}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* User info */}
          {/* Decorative gradient line */}
          <div className="mx-4 gradient-line" />
          <div className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-violet-500/20 text-primary font-semibold ring-2 ring-primary/20">
                {user?.full_name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.full_name}</p>
                <p className="text-xs text-muted-foreground truncate">{maskEmail(user?.email || '')}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={handleLogout} className="text-destructive hover:bg-destructive/10">
                <LogOut className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-72">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between h-16 px-4 lg:px-8 bg-background/80 backdrop-blur-xl border-b border-border/70">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={toggleSidebar}>
              <Menu className="w-5 h-5" />
            </Button>

            {/* Search */}
            <div className="hidden sm:flex relative input-glow rounded-lg transition-all duration-300">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Ara..."
                className="w-64 pl-9 h-9 rounded-lg bg-muted/60 border border-transparent focus-visible:border-input"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            {user?.is_admin && (
              <Button variant="outline" size="sm" className="h-9" onClick={handleExitAdminContext}>
                Admin'a Dön
              </Button>
            )}
            <Link href="/dashboard/bots" className="hidden sm:block">
              <Button size="sm" className="h-9">
                <Plus className="mr-2 h-4 w-4" />
                Yeni Bot
              </Button>
            </Link>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-9 gap-2">
                  <span className="hidden sm:inline">{tenant?.name || 'Tenant'}</span>
                  <ChevronsUpDown className="h-4 w-4 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem className="flex items-center gap-2">
                  <User className="h-4 w-4" />
                  {tenant?.name || 'Tenant'}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Tenant değiştir (yakında)</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

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

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="rounded-full border border-primary/30 ring-2 ring-primary/10 hover:ring-primary/20 transition-all">
                  <span className="text-sm font-semibold bg-gradient-to-br from-primary to-violet-500 bg-clip-text text-transparent">{user?.full_name?.charAt(0).toUpperCase() || 'U'}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem className="gap-2">
                  <User className="h-4 w-4" />
                  Profil
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="gap-2 text-destructive">
                  <LogOut className="h-4 w-4" />
                  Çıkış Yap
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Page content */}
        <main className="p-0">
          {children}
        </main>
      </div>
    </div>
  )
}
