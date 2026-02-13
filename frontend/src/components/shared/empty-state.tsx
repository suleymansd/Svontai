import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn(
      'relative flex flex-col items-center justify-center rounded-2xl border border-dashed border-border/70 bg-card/50 px-6 py-10 text-center overflow-hidden',
      className
    )}>
      {/* Subtle mesh background */}
      <div className="absolute inset-0 mesh-gradient-bg opacity-50 pointer-events-none" />
      <div className="relative z-10 flex flex-col items-center">
        {icon && (
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/15 to-accent animate-float">
            {icon}
          </div>
        )}
        <h3 className="text-base font-semibold">{title}</h3>
        {description && <p className="mt-2 max-w-md text-sm text-muted-foreground">{description}</p>}
        {action && <div className="mt-5">{action}</div>}
      </div>
    </div>
  )
}
