'use client'

import Image from 'next/image'
import { cn } from '@/lib/utils'

interface LogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  showText?: boolean
  showTagline?: boolean
  animated?: boolean
  className?: string
}

export function Logo({ 
  size = 'md', 
  showText = true, 
  showTagline = false,
  animated = false,
  className
}: LogoProps) {
  const sizes = {
    sm: { icon: 32, text: 'text-lg', tagline: 'text-[10px]' },
    md: { icon: 40, text: 'text-xl', tagline: 'text-xs' },
    lg: { icon: 48, text: 'text-2xl', tagline: 'text-sm' },
    xl: { icon: 64, text: 'text-4xl', tagline: 'text-base' },
  }

  const { icon, text, tagline } = sizes[size]

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {/* Logo Image */}
      <div className="relative" style={{ width: icon, height: icon }}>
        <Image
          src="/logo.png"
          alt="SvontAi Logo"
          width={icon}
          height={icon}
          className="object-contain"
          priority
        />
      </div>

      {/* Text */}
      {showText && (
        <div className="flex flex-col">
          <span className={cn('font-bold tracking-tight', text)}>
            Svont<span className="rainbow-text">Ai</span>
          </span>
          {showTagline && (
            <span className={cn('text-muted-foreground -mt-1', tagline)}>
              AI Workflow Optimizer
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export function LogoIcon({ size = 40, className }: { size?: number; className?: string }) {
  return (
    <div className={cn('relative', className)} style={{ width: size, height: size }}>
      <Image
        src="/logo.png"
        alt="SvontAi Logo"
        width={size}
        height={size}
        className="object-contain"
        priority
      />
    </div>
  )
}
