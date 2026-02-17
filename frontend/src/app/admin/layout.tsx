'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'
import { userApi } from '@/lib/api'
import { clearAdminTenantContext, getAdminTenantContext } from '@/lib/admin-tenant-context'
import { decodeJwtPayload } from '@/lib/jwt'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import {
  LayoutDashboard,
  Users,
  Building2,
  Settings,
  LogOut,
  Menu,
  X,
  Shield,
  Activity,
  ChevronLeft,
  User,
  Boxes,
  Package,
  LifeBuoy,
  AlertTriangle,
  BookOpen
} from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'

const navigation = [
  { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
  { name: 'Kullanıcılar', href: '/admin/users', icon: Users },
  { name: 'Müşteriler', href: '/admin/customers', icon: Building2 },
  { name: 'Tenantlar', href: '/admin/tenants', icon: Building2 },
  { name: 'Planlar', href: '/admin/plans', icon: Package },
  { name: 'Araçlar', href: '/admin/tools', icon: Boxes },
  { name: 'Tickets', href: '/admin/tickets', icon: LifeBuoy },
  { name: 'Hata Merkezi', href: '/admin/errors', icon: AlertTriangle },
  { name: 'Kullanım Rehberi', href: '/admin/help', icon: BookOpen },
  { name: 'Incidents', href: '/admin/incidents', icon: Activity },
  { name: 'Audit Logs', href: '/admin/audit', icon: Shield },
  { name: 'Ayarlar', href: '/admin/settings', icon: Settings },
]

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const router = useRouter()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [user, setUser] = useState<{ full_name: string; email: string; is_admin: boolean } | null>(null)
  const [tenantContext, setTenantContext] = useState<{ id: string; name?: string } | null>(null)

  useEffect(() => {
    // Check if user is admin
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('access_token')
        if (!token) {
          router.push('/admin/login')
          return
        }

        const payload = decodeJwtPayload(token)
        const portal = (payload?.portal || 'tenant') as string
        if (portal !== 'super_admin') {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          clearAdminTenantContext()
          router.push('/admin/login')
          return
        }

        const response = await userApi.getMe()
        const user = response.data
        if (!user.is_admin) {
          router.push('/dashboard')
          return
        }
        setUser(user)
        setTenantContext(getAdminTenantContext())
      } catch (error) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        clearAdminTenantContext()
        router.push('/admin/login')
      }
    }

    checkAuth()
  }, [router])

  useEffect(() => {
    const syncTenantContext = () => setTenantContext(getAdminTenantContext())
    window.addEventListener('storage', syncTenantContext)
    return () => window.removeEventListener('storage', syncTenantContext)
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    clearAdminTenantContext()
    router.push('/login')
  }

  const handleOpenCustomerPanel = () => {
    if (!tenantContext?.id) {
      router.push('/admin/tenants')
      return
    }
    router.push('/dashboard')
  }

  const handleClearTenantContext = () => {
    clearAdminTenantContext()
    setTenantContext(null)
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-transparent" style={{ borderImage: 'linear-gradient(135deg, hsl(var(--primary)), hsl(262 83% 58%)) 1' }}></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={cn(
        "fixed top-0 left-0 z-50 h-full w-72 bg-card/95 backdrop-blur-xl border-r border-border/70 transform transition-transform duration-300 lg:translate-x-0",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-border/70">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Icon3DBadge icon={Shield} from="from-primary" to="to-violet-500" />
                <div>
                  <h1 className="text-lg font-bold">Admin Panel</h1>
                  <p className="text-xs text-muted-foreground">SvontAi Yönetim</p>
                </div>
              </div>
              <button
                className="lg:hidden text-muted-foreground hover:text-foreground"
                onClick={() => setSidebarOpen(false)}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Back to Dashboard */}
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-6 py-3 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Dashboard'a Dön
          </Link>

          {/* Navigation */}
          <nav className="flex-1 px-4 py-4 space-y-1">
            {navigation.map((item) => {
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200",
                    isActive
                      ? "nav-active-glow text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                  )}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon3DBadge
                    icon={item.icon}
                    size="sm"
                    active
                    from={isActive ? "from-primary" : "from-slate-200 dark:from-slate-800"}
                    to={isActive ? "to-violet-500" : "to-slate-50 dark:to-slate-700"}
                    className={cn(
                      "transition-transform duration-200 group-hover:-translate-y-0.5",
                      isActive && "ring-2 ring-primary/25"
                    )}
                  />
                  {item.name}
                </Link>
              )
            })}
          </nav>

          {/* User Info & Logout */}
          <div className="p-4 border-t border-border/70">
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl glass-card mb-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary/20 to-violet-500/20 text-primary flex items-center justify-center font-semibold ring-2 ring-primary/20">
                {user.full_name?.charAt(0)?.toUpperCase() || 'A'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user.full_name}</p>
                <p className="text-xs text-muted-foreground truncate">{user.email}</p>
              </div>
              <div className="px-2 py-1 bg-gradient-to-r from-primary/15 to-violet-500/15 rounded-full">
                <span className="text-xs text-primary font-medium">Admin</span>
              </div>
            </div>
            <Button
              variant="ghost"
              className="w-full justify-start text-muted-foreground hover:text-foreground hover:bg-muted"
              onClick={handleLogout}
            >
              <LogOut className="w-5 h-5 mr-3" />
              Çıkış Yap
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="lg:pl-72">
        {/* Top Bar */}
        <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-xl border-b border-border/70">
          <div className="flex items-center justify-between h-16 px-4 lg:px-8">
            <button
              className="lg:hidden p-2 text-muted-foreground hover:text-foreground"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-6 h-6" />
            </button>

            <div className="flex items-center gap-2 text-sm">
              <Activity className="w-4 h-4 text-success animate-pulse" />
              <span className="text-muted-foreground">Sistem durumu:</span>
              <span className="text-success font-medium">Çalışıyor</span>
            </div>

            <div className="flex items-center gap-4">
              <div className="hidden md:flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleOpenCustomerPanel}>
                  {tenantContext?.id ? `Müşteri: ${tenantContext?.name || tenantContext.id}` : 'Tenant Seç'}
                </Button>
                {tenantContext?.id && (
                  <Button variant="ghost" size="sm" onClick={handleClearTenantContext}>
                    Temizle
                  </Button>
                )}
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="rounded-full border border-border/60">
                    <span className="text-sm font-semibold">{user.full_name?.charAt(0)?.toUpperCase() || 'A'}</span>
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
          </div>
        </header>

        {/* Page Content */}
        <main className="p-0">
          {children}
        </main>
      </div>
    </div>
  )
}
