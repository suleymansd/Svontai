import { ReactNode, isValidElement } from 'react'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

interface KPIStatProps {
  label: string
  value: string | number
  icon?: ReactNode
  trend?: string
  tone?: 'neutral' | 'positive' | 'negative' | 'warning'
  className?: string
}

const toneMap = {
  neutral: 'text-muted-foreground',
  positive: 'text-success',
  negative: 'text-destructive',
  warning: 'text-warning',
}

export function KPIStat({ label, value, icon, trend, tone = 'neutral', className }: KPIStatProps) {
  const iconComponent = isValidElement(icon) ? (icon.type as any) : null
  const toneGradient = {
    neutral: { from: 'from-primary', to: 'to-violet-500' },
    positive: { from: 'from-emerald-500', to: 'to-teal-500' },
    negative: { from: 'from-red-500', to: 'to-rose-500' },
    warning: { from: 'from-amber-500', to: 'to-orange-500' },
  }[tone]

  return (
    <Card className={cn(
      'border border-border/70 bg-card/95 p-5 shadow-soft card-hover-lift gradient-border-animated group',
      className
    )}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="mt-2 text-2xl font-semibold transition-transform duration-300 group-hover:scale-105 origin-left">{value}</p>
          {trend && <p className={cn('mt-1 text-xs font-medium', toneMap[tone])}>{trend}</p>}
        </div>
        {iconComponent ? (
          <Icon3DBadge
            icon={iconComponent}
            from={toneGradient.from}
            to={toneGradient.to}
            className="animate-pulse-glow"
          />
        ) : icon ? (
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 text-primary animate-pulse-glow">
            {icon}
          </div>
        ) : null}
      </div>
    </Card>
  )
}
