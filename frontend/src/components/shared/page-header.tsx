import { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Breadcrumbs, BreadcrumbItem } from './breadcrumbs'

interface PageHeaderProps {
  title: string
  description?: string
  breadcrumbs?: BreadcrumbItem[]
  actions?: ReactNode
  icon?: ReactNode
  className?: string
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  icon,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn('space-y-3 animate-slide-up', className)}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs items={breadcrumbs} />
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            {icon}
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl gradient-text-vivid">{title}</h1>
          </div>
          {description && (
            <p className="text-sm text-muted-foreground sm:text-base">{description}</p>
          )}
          {/* Animated gradient accent line */}
          <div className="gradient-line mt-3 w-24 rounded-full" />
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  )
}
