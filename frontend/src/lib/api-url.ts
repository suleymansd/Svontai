export function normalizeApiUrl(value?: string): string {
  const raw = (value || '').trim()
  if (!raw) {
    throw new Error('NEXT_PUBLIC_BACKEND_URL is required. Set it to the SmartWA backend URL.')
  }
  if (/^https?:\/\//i.test(raw)) return raw.replace(/\/+$/, '')
  return `https://${raw.replace(/\/+$/, '')}`
}
