import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { ButtonHTMLAttributes } from 'react'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'secondary' | 'ghost' | 'outline' | 'destructive'
  size?: 'icon' | 'sm' | 'md'
  label: string
}

export function IconButton({ variant = 'ghost', size = 'icon', label, className, ...props }: IconButtonProps) {
  const premiumChrome = variant === 'default' || variant === 'destructive'
    ? 'h-9 w-9 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all'
    : 'h-9 w-9 border border-border/60 bg-muted/30 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all'

  return (
    <Button
      variant={variant}
      size={size === 'md' ? 'icon' : size}
      className={cn(
        premiumChrome,
        className
      )}
      aria-label={label}
      {...props}
    />
  )
}
