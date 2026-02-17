export type JwtPayload = Record<string, any>

function base64UrlDecode(value: string): string {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
  return decodeURIComponent(
    Array.prototype.map
      .call(atob(padded), (c: string) => `%${(`00${c.charCodeAt(0).toString(16)}`).slice(-2)}`)
      .join('')
  )
}

export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const json = base64UrlDecode(parts[1])
    return JSON.parse(json)
  } catch {
    return null
  }
}

