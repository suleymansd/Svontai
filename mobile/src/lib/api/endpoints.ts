import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { getOrCreateDeviceId, setRefreshToken } from '@/lib/auth/session-vault';
import { apiRequest, clearMobileSession, setAccessToken } from './client';
import type {
  ActionCenter,
  Appointment,
  Conversation,
  DashboardStats,
  MeContext,
  Message,
  MobileTokenResponse,
  OperationalReport,
  OperatorSendResult,
  WorkspaceNote,
} from './types';

export async function login(email: string, password: string, twoFactorCode?: string): Promise<void> {
  const deviceId = await getOrCreateDeviceId();
  const tokens = await apiRequest<MobileTokenResponse>('/auth/login', {
    method: 'POST',
    authenticated: false,
    body: JSON.stringify({
      email: email.trim().toLowerCase(),
      password,
      two_factor_code: twoFactorCode || undefined,
      portal: 'tenant',
      client: 'mobile',
      device_id: deviceId,
      device_name: Device.modelName || Device.deviceName || 'Mobil cihaz',
      platform: Platform.OS,
      app_version: Constants.expoConfig?.version || '1.0.0',
    }),
  });
  setAccessToken(tokens.access_token);
  await setRefreshToken(tokens.refresh_token);
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<{ success: boolean }>('/auth/logout', { method: 'POST', retry: false });
  } finally {
    await clearMobileSession();
  }
}

export const getMe = () => apiRequest<MeContext>('/api/me');
export const getDashboardStats = () => apiRequest<DashboardStats>('/analytics/dashboard');
export const getActionCenter = () => apiRequest<ActionCenter>('/analytics/action-center');
export const getConversations = () => apiRequest<Conversation[]>('/conversations?limit=100');
export const getConversationMessages = (id: string) =>
  apiRequest<Message[]>(`/operator/conversation/${encodeURIComponent(id)}/messages?limit=100`);
export const setConversationAIReply = (id: string, enabled: boolean) =>
  apiRequest<Conversation>(`/conversations/${encodeURIComponent(id)}/ai-reply`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled }),
  });
export const getAppointments = () => apiRequest<Appointment[]>('/appointments');
export const getOperationalReport = (period: 'today' | 'week') =>
  apiRequest<OperationalReport>(`/analytics/operational-report?period=${period}`);
export const getWorkspaceNotes = () => apiRequest<WorkspaceNote[]>('/notes?archived=false');
export const createWorkspaceNote = (data: {
  title: string;
  content: string;
  color?: WorkspaceNote['color'];
  pinned?: boolean;
}) => apiRequest<WorkspaceNote>('/notes', { method: 'POST', body: JSON.stringify(data) });
export const updateWorkspaceNote = (
  id: string,
  data: Partial<Pick<WorkspaceNote, 'title' | 'content' | 'color' | 'pinned' | 'archived'>>,
) => apiRequest<WorkspaceNote>(`/notes/${encodeURIComponent(id)}`, {
  method: 'PATCH',
  body: JSON.stringify(data),
});
export const sendOperatorMessage = (conversationId: string, content: string) =>
  apiRequest<OperatorSendResult>('/operator/send-message', {
    method: 'POST',
    body: JSON.stringify({ conversation_id: conversationId, content }),
  });

export async function requestEmailVerification(email: string) {
  return apiRequest<{ message: string; verified?: boolean }>('/auth/email-verification/request', {
    method: 'POST',
    authenticated: false,
    body: JSON.stringify({ email: email.trim().toLowerCase() }),
  });
}

export async function confirmEmailVerification(email: string, code: string) {
  return apiRequest<{ message: string; verified: boolean }>('/auth/email-verification/confirm', {
    method: 'POST',
    authenticated: false,
    body: JSON.stringify({ email: email.trim().toLowerCase(), code }),
  });
}
