'use client'

import type { ComponentType } from 'react'
import { cn } from '@/lib/utils'

type Size = 'sm' | 'md'

const sizeClasses: Record<Size, { wrapper: string; icon: string }> = {
  sm: { wrapper: 'h-8 w-8 rounded-xl', icon: 'h-4 w-4' },
  md: { wrapper: 'h-11 w-11 rounded-2xl', icon: 'h-5 w-5' },
}

export function Icon3DBadge({
  icon: Icon,
  size = 'md',
  active = true,
  from = 'from-slate-500',
  to = 'to-slate-700',
  className,
}: {
  icon: ComponentType<{ className?: string }>
  size?: Size
  active?: boolean
  from?: string
  to?: string
  className?: string
}) {
  const wrapperSize = sizeClasses[size].wrapper
  const iconSize = sizeClasses[size].icon

  return (
    <div
      className={cn(
        'relative flex items-center justify-center',
        wrapperSize,
        'shadow-[0_14px_30px_rgba(0,0,0,0.20)]',
        active ? `bg-gradient-to-br ${from} ${to}` : 'bg-muted/60',
        'after:absolute after:inset-0 after:rounded-[inherit] after:shadow-[inset_0_1px_0_rgba(255,255,255,0.55),inset_0_-1px_0_rgba(0,0,0,0.18)] after:content-[\"\"]',
        'before:absolute before:inset-[1px] before:rounded-[inherit] before:bg-gradient-to-b before:from-white/35 before:to-white/0 before:content-[\"\"]',
        className
      )}
      aria-hidden="true"
    >
      <div className={cn(
        'relative z-10 flex items-center justify-center drop-shadow-[0_10px_18px_rgba(0,0,0,0.32)]',
        active ? 'text-white' : 'text-muted-foreground'
      )}>
        <Icon className={iconSize} />
      </div>
    </div>
  )
}

