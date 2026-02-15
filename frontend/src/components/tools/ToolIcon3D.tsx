'use client'

import { cn } from '@/lib/utils'
import { getToolCatalogItem } from './catalog'

type Size = 'sm' | 'md' | 'lg'

const sizeClasses: Record<Size, { wrapper: string; icon: string }> = {
  sm: { wrapper: 'h-9 w-9 rounded-xl', icon: 'h-4 w-4' },
  md: { wrapper: 'h-12 w-12 rounded-2xl', icon: 'h-5 w-5' },
  lg: { wrapper: 'h-16 w-16 rounded-3xl', icon: 'h-7 w-7' },
}

export function ToolIcon3D({
  toolId,
  size = 'md',
  active = true,
  className,
}: {
  toolId: string
  size?: Size
  active?: boolean
  className?: string
}) {
  const catalogItem = getToolCatalogItem(toolId)
  const Icon = catalogItem?.menuIcon
  const accentFrom = catalogItem?.accent.from ?? 'from-slate-500'
  const accentTo = catalogItem?.accent.to ?? 'to-slate-700'

  const wrapperSize = sizeClasses[size].wrapper
  const iconSize = sizeClasses[size].icon

  return (
    <div
      className={cn(
        'relative flex items-center justify-center',
        wrapperSize,
        'shadow-[0_14px_30px_rgba(0,0,0,0.22)]',
        active ? `bg-gradient-to-br ${accentFrom} ${accentTo}` : 'bg-muted/60',
        'after:absolute after:inset-0 after:rounded-[inherit] after:shadow-[inset_0_1px_0_rgba(255,255,255,0.55),inset_0_-1px_0_rgba(0,0,0,0.18)] after:content-[\"\"]',
        'before:absolute before:inset-[1px] before:rounded-[inherit] before:bg-gradient-to-b before:from-white/35 before:to-white/0 before:content-[\"\"]',
        className
      )}
      aria-hidden="true"
    >
      <div className="relative z-10 flex items-center justify-center text-white drop-shadow-[0_10px_18px_rgba(0,0,0,0.35)]">
        {Icon ? <Icon className={iconSize} /> : <span className="text-sm font-semibold">T</span>}
      </div>
    </div>
  )
}

