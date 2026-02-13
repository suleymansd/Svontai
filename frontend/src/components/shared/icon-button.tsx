import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { ButtonHTMLAttributes } from 'react'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'secondary' | 'ghost' | 'outline' | 'destructive'
  size?: 'icon' | 'sm' | 'md'
  label: string
}

export function IconButton({ variant = 'ghost', size = 'icon', label, className, ...props }: IconButtonProps) {
  return (
    <Button
      variant={variant}
      size={size === 'md' ? 'icon' : size}
      className={cn('h-9 w-9', className)}
      aria-label={label}
      {...props}
    />
  )
}
