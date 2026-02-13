import { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'

interface SectionCardProps {
  title: string
  description?: string
  children: ReactNode
  className?: string
  actions?: ReactNode
}

export function SectionCard({ title, description, children, className, actions }: SectionCardProps) {
  return (
    <Card className={cn('border border-border/70 bg-card/95 shadow-soft card-hover-lift accent-bar', className)}>
      <div className="flex flex-col gap-4 border-b border-border/70 px-6 py-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      <div className="px-6 py-5">{children}</div>
    </Card>
  )
}
