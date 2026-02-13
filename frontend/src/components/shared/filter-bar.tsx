import { ReactNode } from 'react'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Input } from '@/components/ui/input'

interface FilterBarProps {
  searchPlaceholder?: string
  onSearchChange?: (value: string) => void
  filters?: ReactNode
  actions?: ReactNode
  className?: string
}

export function FilterBar({ searchPlaceholder = 'Ara...', onSearchChange, filters, actions, className }: FilterBarProps) {
  return (
    <div className={cn(
      'flex flex-col gap-3 rounded-2xl border border-border/70 glass-card p-3 sm:flex-row sm:items-center sm:justify-between',
      className
    )}>
      <div className="relative w-full sm:max-w-xs input-glow rounded-lg transition-all duration-300">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder={searchPlaceholder}
          className="h-9 pl-9"
          onChange={(event) => onSearchChange?.(event.target.value)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {filters}
        {actions}
      </div>
    </div>
  )
}
