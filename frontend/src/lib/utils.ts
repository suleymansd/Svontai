import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('tr-TR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(date))
}

export function formatDateTime(date: string | Date): string {
  return new Intl.DateTimeFormat('tr-TR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date))
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

export function maskSecret(value: string, visiblePrefix: number = 4, visibleSuffix: number = 4): string {
  const raw = (value || '').trim()
  if (!raw) return ''
  if (raw.length <= visiblePrefix + visibleSuffix + 3) return raw
  return `${raw.slice(0, visiblePrefix)}…${raw.slice(-visibleSuffix)}`
}

export function maskEmail(email: string): string {
  const raw = (email || '').trim()
  if (!raw) return ''
  const [userPart, domainPart] = raw.split('@')
  if (!domainPart) return maskSecret(raw, 2, 2)
  if (userPart.length <= 2) return `${userPart[0] || '*'}*@${domainPart}`
  return `${userPart[0]}***${userPart.slice(-1)}@${domainPart}`
}
