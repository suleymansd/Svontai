import Constants from 'expo-constants';

import {
  clearRefreshToken,
  getOrCreateDeviceId,
  getRefreshToken,
  setRefreshToken,
} from '@/lib/auth/session-vault';
import type { MobileTokenResponse } from './types';

const configuredApiUrl = process.env.EXPO_PUBLIC_API_URL || Constants.expoConfig?.extra?.apiUrl;
export const API_URL = String(configuredApiUrl || '').replace(/\/+$/, '');

let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
let onSessionExpired: (() => void) | null = null;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export async function openRealtimeStream(signal: AbortSignal): Promise<Response> {
  const { fetch: streamFetch } = await import('expo/fetch');
  if (!API_URL) throw new ApiError('Mobil API adresi yapılandırılmamış.', 500);
  let token = accessToken || await refreshAccessToken();
  const connect = () => streamFetch(`${API_URL}/realtime/events`, {
    headers: { Accept: 'text/event-stream', Authorization: `Bearer ${token}` }, signal,
  });
  let response = await connect();
  if (response.status === 401) {
    await response.text();
    token = await refreshAccessToken();
    response = await connect();
  }
  if (!response.ok) throw new ApiError('Canlı bağlantı kurulamadı.', response.status);
  return response;
}

function errorFromBody(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === 'string') return new ApiError(detail, status, undefined, body);
  if (detail && typeof detail === 'object') {
    const value = detail as { message?: string; code?: string };
    return new ApiError(value.message || 'İşlem tamamlanamadı.', status, value.code, body);
  }
  return new ApiError('Sunucuya ulaşılamadı. Lütfen tekrar deneyin.', status, undefined, body);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError('Sunucudan geçersiz yanıt alındı.', response.status || 500);
  }
  if (!response.ok) throw errorFromBody(response.status, body);
  return body as T;
}

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const [refreshToken, deviceId] = await Promise.all([getRefreshToken(), getOrCreateDeviceId()]);
    if (!refreshToken) throw new ApiError('Oturum bulunamadı.', 401);

    const response = await fetchWithTimeout(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken, device_id: deviceId }),
    });
    const tokens = await parseResponse<MobileTokenResponse>(response);
    accessToken = tokens.access_token;
    await setRefreshToken(tokens.refresh_token);
    return tokens.access_token;
  })();

  try {
    return await refreshPromise;
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      accessToken = null;
      await clearRefreshToken();
      onSessionExpired?.();
    }
    throw error;
  } finally {
    refreshPromise = null;
  }
}

type RequestOptions = RequestInit & { authenticated?: boolean; retry?: boolean };

async function fetchWithTimeout(url: string, options: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  const timer = setTimeout(abort, 20_000);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', abort);
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!API_URL) throw new ApiError('Mobil API adresi yapılandırılmamış.', 500);

  const { authenticated = true, retry = true, headers, ...requestOptions } = options;
  const requestHeaders = new Headers(headers);
  requestHeaders.set('Accept', 'application/json');
  if (requestOptions.body && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json');
  }
  if (authenticated && accessToken) requestHeaders.set('Authorization', `Bearer ${accessToken}`);

  const response = await fetchWithTimeout(`${API_URL}${path}`, { ...requestOptions, headers: requestHeaders });
  if (response.status === 401 && authenticated && retry) {
    const token = await refreshAccessToken();
    requestHeaders.set('Authorization', `Bearer ${token}`);
    return apiRequest<T>(path, { ...options, headers: requestHeaders, retry: false });
  }
  return parseResponse<T>(response);
}

export async function restoreMobileSession(): Promise<boolean> {
  if (!(await getRefreshToken())) return false;
  await refreshAccessToken();
  return true;
}

export async function clearMobileSession(): Promise<void> {
  accessToken = null;
  await clearRefreshToken();
}
