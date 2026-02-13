import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface MetaRowProps {
  label: string
  value: ReactNode
  className?: string
}

export function MetaRow({ label, value, className }: MetaRowProps) {
  return (
    <div className={cn('flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between', className)}>
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-foreground">{value}</span>
    </div>
  )
}
