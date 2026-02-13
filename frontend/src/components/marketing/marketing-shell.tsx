'use client'

import Link from 'next/link'
import { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/Logo'
import { cn } from '@/lib/utils'

const navItems = [
  { label: 'Özellikler', href: '/features' },
  { label: 'Fiyatlar', href: '/pricing' },
  { label: 'Use Cases', href: '/use-cases/real-estate' },
  { label: 'Güvenlik', href: '/security' },
  { label: 'Dokümantasyon', href: '/docs' },
  { label: 'İletişim', href: '/contact' },
]

interface MarketingShellProps {
  children: ReactNode
  className?: string
}

export function MarketingShell({ children, className }: MarketingShellProps) {
  return (
    <div className={cn('min-h-screen bg-background text-foreground', className)}>
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2">
            <Logo size="md" showText={true} animated={false} />
          </Link>
          <nav className="hidden items-center gap-6 lg:flex">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link href="/login" className="hidden sm:block">
              <Button variant="ghost" size="sm">Giriş Yap</Button>
            </Link>
            <Link href="/register">
              <Button size="sm" className="rounded-full px-5">Ücretsiz Başla</Button>
            </Link>
          </div>
        </div>
      </header>

      <main>{children}</main>

      <footer className="border-t border-border/60 bg-card/30">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 lg:grid-cols-12 lg:px-8">
          <div className="lg:col-span-4">
            <Logo size="md" showText={true} animated={false} />
            <p className="mt-4 text-sm text-muted-foreground">
              SvontAI, WhatsApp tabanlı müşteri deneyimini otomasyonlarla ölçeklendirmenizi sağlayan modern destek platformudur.
            </p>
          </div>
          <div className="lg:col-span-8 grid grid-cols-2 gap-6 sm:grid-cols-3">
            <div className="space-y-3">
              <p className="text-sm font-semibold">Ürün</p>
              <div className="space-y-2 text-sm text-muted-foreground">
                <Link href="/features" className="block hover:text-foreground">Özellikler</Link>
                <Link href="/pricing" className="block hover:text-foreground">Fiyatlar</Link>
                <Link href="/use-cases/real-estate" className="block hover:text-foreground">Use Cases</Link>
              </div>
            </div>
            <div className="space-y-3">
              <p className="text-sm font-semibold">Şirket</p>
              <div className="space-y-2 text-sm text-muted-foreground">
                <Link href="/security" className="block hover:text-foreground">Güvenlik</Link>
                <Link href="/contact" className="block hover:text-foreground">İletişim</Link>
                <Link href="/docs" className="block hover:text-foreground">Dokümantasyon</Link>
              </div>
            </div>
            <div className="space-y-3">
              <p className="text-sm font-semibold">Kaynaklar</p>
              <div className="space-y-2 text-sm text-muted-foreground">
                <Link href="/docs" className="block hover:text-foreground">Dokümantasyon</Link>
                <Link href="/security" className="block hover:text-foreground">Güvenlik</Link>
                <Link href="/contact" className="block hover:text-foreground">İletişim</Link>
              </div>
            </div>
          </div>
        </div>
        <div className="border-t border-border/60">
          <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:px-6 lg:px-8">
            <span>© 2026 SvontAI. Tüm hakları saklıdır.</span>
            <span>Automation OS for WhatsApp-first teams.</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
