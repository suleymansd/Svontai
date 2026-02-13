import { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'

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
        {icon && (
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 text-primary animate-pulse-glow">
            {icon}
          </div>
        )}
      </div>
    </Card>
  )
}
