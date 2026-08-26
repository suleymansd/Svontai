let accessToken: string | null = null
let refreshPromise: Promise<string> | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token?.trim() || null
}

export function clearAccessToken(): void {
  accessToken = null
}

export function getRefreshPromise(): Promise<string> | null {
  return refreshPromise
}

export function setRefreshPromise(promise: Promise<string> | null): void {
  refreshPromise = promise
}
