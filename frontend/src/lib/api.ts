import axios from 'axios'
import { ADMIN_TENANT_CONTEXT_ID_KEY } from './admin-tenant-context'
import { normalizeApiUrl } from './api-url'
import { normalizeTrackedApiPath, trackProductEvent } from './product-analytics'
import {
  clearAccessToken,
  getAccessToken,
  getRefreshPromise,
  setAccessToken,
  setRefreshPromise,
} from './auth-token'

export const API_URL = normalizeApiUrl(process.env.NEXT_PUBLIC_BACKEND_URL)

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    const tenantContextId = localStorage.getItem(ADMIN_TENANT_CONTEXT_ID_KEY)
    const headers = config.headers as Record<string, string>
    if (tenantContextId) {
      headers['X-Tenant-ID'] = tenantContextId
    } else {
      delete headers['X-Tenant-ID']
    }
  }
  return config
})

// Handle token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const requestUrl = String(originalRequest?.url || '')
    const isAuthRoute = requestUrl.startsWith('/auth/')

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthRoute) {
      originalRequest._retry = true

      try {
        const access_token = await refreshAccessToken()

        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        // Refresh failed, redirect to login
        clearAccessToken()
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      }
    }

    const trackedPath = normalizeTrackedApiPath(requestUrl)
    if (!trackedPath.startsWith('/product-analytics/')) {
      trackProductEvent(
        'api_error',
        {
          status: Number(error.response?.status || 0),
          method: String(originalRequest?.method || 'get').toUpperCase(),
          route: trackedPath,
        },
        'error',
        trackedPath,
      )
    }
    return Promise.reject(error)
  }
)

export async function refreshAccessToken(): Promise<string> {
  const activeRefresh = getRefreshPromise()
  if (activeRefresh) return activeRefresh

  const refresh = axios
    .post('/api/auth/refresh', {}, { withCredentials: true })
    .then((response) => {
      const token = String(response.data?.access_token || '').trim()
      if (!token) throw new Error('Refresh response did not include an access token')
      setAccessToken(token)
      return token
    })
    .catch((error) => {
      clearAccessToken()
      throw error
    })
    .finally(() => setRefreshPromise(null))

  setRefreshPromise(refresh)
  return refresh
}

// Auth API
export const authApi = {
  register: (data: {
    email: string
    password: string
    full_name: string
    terms_accepted: boolean
    privacy_notice_acknowledged: boolean
    terms_version: string
    privacy_version: string
    kvkk_notice_version: string
  }) =>
    api.post('/auth/register', data),
  
  login: (data: {
    email: string
    password: string
    two_factor_code?: string
    portal?: 'tenant' | 'super_admin'
    admin_session_note?: string
  }) =>
    axios.post('/api/auth/login', data, { withCredentials: true }),
  
  refresh: refreshAccessToken,
  refreshWithCookie: refreshAccessToken,
  logout: () => {
    const token = getAccessToken()
    return axios.post(
      '/api/auth/logout',
      {},
      {
        withCredentials: true,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    )
  },

  requestPasswordReset: (email: string) =>
    api.post('/auth/password-reset/request', { email }),

  confirmPasswordReset: (data: { email: string; code: string; new_password: string }) =>
    api.post('/auth/password-reset/confirm', data),

  requestEmailVerification: (email: string) =>
    api.post('/auth/email-verification/request', { email }),

  confirmEmailVerification: (data: { email: string; code: string }) =>
    api.post('/auth/email-verification/confirm', data),

  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),

  getTwoFactorStatus: () => api.get('/auth/2fa/status'),

  setupTwoFactor: (data: { current_password: string }) =>
    api.post('/auth/2fa/setup', data),

  enableTwoFactor: (data: { code: string }) =>
    api.post('/auth/2fa/enable', data),

  disableTwoFactor: (data: { current_password: string; code: string }) =>
    api.post('/auth/2fa/disable', data),

  enableAdminTwoFactor: (data: { setup_token: string; code: string }) =>
    api.post('/auth/admin/2fa/enable', data),
}

// User API
export const userApi = {
  getMe: () => api.get('/me'),
  updateMe: (data: { full_name?: string; email?: string }) =>
    api.put('/me', data),
}

export const meApi = {
  getContext: () => api.get('/api/me'),
}

// Tenant API
export const tenantApi = {
  getMyTenants: () => api.get('/tenants/my'),
  createTenant: (data: { name: string }) => api.post('/tenants', data),
  updateTenant: (id: string, data: { name?: string }) =>
    api.put(`/tenants/${id}`, data),
}

// Bot API
export const botApi = {
  list: () => api.get('/bots'),
  getAssistantProfile: () => api.get('/bots/assistant-profile'),
  updateAssistantTraining: (data: {
    goal: 'support' | 'sales' | 'appointments' | 'mixed'
    tone: 'formal' | 'friendly' | 'professional' | 'casual'
    response_length: 'concise' | 'balanced' | 'detailed'
    price_policy: 'known_only' | 'confirm_before_sending' | 'never_share'
    handoff_mode: 'automatic' | 'suggest' | 'manual'
    business_summary: string
  }) => api.put('/bots/assistant-profile/training', data),
  updateAssistantCapability: (key: string, data: { enabled: boolean; config?: Record<string, unknown> }) =>
    api.patch(`/bots/assistant-profile/capabilities/${key}`, data),
  get: (id: string) => api.get(`/bots/${id}`),
  simulate: (id: string, data: {
    message: string
    history: Array<{ role: 'customer' | 'assistant'; content: string }>
  }) => api.post(`/bots/${id}/simulate`, data),
  trainerMessage: (data: { message: string; session_id?: string | null }) =>
    api.post<AssistantTrainerMessageResponse>('/bots/assistant-profile/trainer/message', data),
  applyTrainerDraft: (sessionId: string) =>
    api.post<AssistantTrainerApplyResponse>(`/bots/assistant-profile/trainer/${sessionId}/apply`),
  create: (data: {
    name: string
    description?: string
    welcome_message?: string
    language?: string
    primary_color?: string
    widget_position?: 'left' | 'right'
  }) => api.post('/bots', data),
  update: (id: string, data: Partial<{
    name: string
    description: string
    welcome_message: string
    language: string
    primary_color: string
    widget_position: 'left' | 'right'
    is_active: boolean
  }>) => api.put(`/bots/${id}`, data),
  delete: (id: string) => api.delete(`/bots/${id}`),
}

export type AssistantTrainerProposal = {
  name: string
  description: string
  example_questions: string[]
  answer: string
  behavior_instruction: string
}

export type AssistantTrainerMessageResponse = {
  session_id: string
  status: 'collecting' | 'ready' | 'applied'
  assistant_message: string
  proposal?: AssistantTrainerProposal | null
  specialist_bot_id?: string | null
}

export type AssistantTrainerApplyResponse = {
  session_id: string
  status: 'applied'
  assistant_message: string
  bot: {
    id: string
    name: string
    description?: string | null
    is_active: boolean
    assistant_type: 'primary' | 'specialist'
  }
  knowledge_items_created: number
}

export type AssistantMediaAsset = {
  id: string
  title: string
  description?: string | null
  media_type: 'image' | 'video' | 'catalog'
  mime_type: string
  file_size_bytes: number
  keywords: string[]
  is_active: boolean
  send_count: number
  last_sent_at?: string | null
  preview_url: string
  created_at: string
  updated_at: string
}

export const mediaApi = {
  list: () => api.get<AssistantMediaAsset[]>('/media'),
  upload: (data: FormData, onUploadProgress?: (progress: number) => void) =>
    api.post<AssistantMediaAsset>('/media', data, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (event.total && onUploadProgress) onUploadProgress(Math.round((event.loaded / event.total) * 100))
      },
    }),
  update: (id: string, data: Partial<Pick<AssistantMediaAsset, 'title' | 'description' | 'keywords' | 'is_active'>>) =>
    api.patch<AssistantMediaAsset>(`/media/${id}`, data),
  delete: (id: string) => api.delete(`/media/${id}`),
}

// Knowledge API
export const knowledgeApi = {
  list: (botId: string) => api.get(`/bots/${botId}/knowledge`),
  create: (botId: string, data: { title: string; question: string; answer: string }) =>
    api.post(`/bots/${botId}/knowledge`, data),
  update: (botId: string, itemId: string, data: Partial<{ title: string; question: string; answer: string }>) =>
    api.put(`/bots/${botId}/knowledge/${itemId}`, data),
  delete: (botId: string, itemId: string) =>
    api.delete(`/bots/${botId}/knowledge/${itemId}`),
}

// Conversation API
export const conversationApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    api.get('/conversations', { params }),
  listByBot: (botId: string, params?: { skip?: number; limit?: number }) =>
    api.get(`/bots/${botId}/conversations`, { params }),
  get: (id: string) => api.get(`/conversations/${id}`),
  getMessages: (id: string, params?: { skip?: number; limit?: number }) =>
    api.get(`/conversations/${id}/messages`, { params }),
}

// Lead API
export const leadApi = {
  list: (params?: { search?: string; bot_id?: string; skip?: number; limit?: number }) =>
    api.get('/leads', { params }),
  listByBot: (botId: string, params?: { skip?: number; limit?: number }) =>
    api.get(`/leads/bots/${botId}`, { params }),
  create: (data: { name: string; email?: string; phone?: string; notes?: string; source?: string }) =>
    api.post('/leads', data),
  update: (id: string, data: Partial<{ name: string; email: string; phone: string; notes: string; status: string }>) =>
    api.put(`/leads/${id}`, data),
  delete: (id: string) => api.delete(`/leads/${id}`),
}

export const callsApi = {
  list: (params?: { status?: string; provider?: string; skip?: number; limit?: number }) =>
    api.get('/calls', { params }),
  get: (id: string) => api.get(`/calls/${id}`),
  transcript: (id: string) => api.get(`/calls/${id}/transcript`),
  summary: (id: string) => api.get(`/calls/${id}/summary`),
}

export const voiceAutomationApi = {
  getCapabilities: () => api.get('/voice-automation/capabilities'),
  getSettings: () => api.get('/voice-automation/settings'),
  updateSettings: (data: Record<string, unknown>) => api.patch('/voice-automation/settings', data),
  listIntents: (params?: { status?: string; limit?: number }) =>
    api.get('/voice-automation/intents', { params }),
  listJobs: (params?: { status?: string; limit?: number }) =>
    api.get('/voice-automation/jobs', { params }),
  cancelJob: (jobId: string) =>
    api.post(`/voice-automation/jobs/${jobId}/cancel`),
  retryJob: (jobId: string, nextAttemptAt?: string) =>
    api.post(`/voice-automation/jobs/${jobId}/retry`, {
      next_attempt_at: nextAttemptAt || null,
    }),
  listContactPolicies: (params?: { status?: 'allowed' | 'do_not_call'; limit?: number }) =>
    api.get('/voice-automation/contact-policies', { params }),
  updateContactPolicy: (data: {
    phone_number: string
    status: 'allowed' | 'do_not_call'
    reason?: string
  }) => api.put('/voice-automation/contact-policies', data),
  testCall: (data: { customer_phone: string; customer_name?: string; reason?: string; consent_confirmed: boolean }) =>
    api.post('/voice-automation/test-call', data),
}

// WhatsApp API
export const whatsappApi = {
  getIntegration: (botId: string) =>
    api.get(`/bots/${botId}/whatsapp-integration`),
  createIntegration: (botId: string, data: {
    whatsapp_phone_number_id: string
    whatsapp_business_account_id: string
    access_token: string
    webhook_verify_token: string
  }) => api.post(`/bots/${botId}/whatsapp-integration`, data),
}

// Admin API
export const adminApi = {
  getStats: () => api.get('/admin/stats'),
  
  // Users
  listUsers: (params?: { page?: number; page_size?: number; search?: string; is_admin?: boolean; is_active?: boolean }) =>
    api.get('/admin/users', { params }),
  getUser: (id: string) => api.get(`/admin/users/${id}`),
  createUser: (data: { email: string; full_name: string; password: string; is_admin?: boolean }) =>
    api.post('/admin/users', data),
  updateUser: (id: string, data: { full_name?: string; email?: string; is_admin?: boolean; is_active?: boolean }) =>
    api.patch(`/admin/users/${id}`, data),
  deleteUser: (id: string) => api.delete(`/admin/users/${id}`),
  makeAdmin: (id: string) => api.post(`/admin/make-admin/${id}`),
  
  // Tenants
  listTenants: (params?: { page?: number; page_size?: number; search?: string }) =>
    api.get('/admin/tenants', { params }),
  getTenant: (id: string) => api.get(`/admin/tenants/${id}`),
  updateTenantFeatureFlags: (id: string, enabled_flags: string[]) =>
    api.patch(`/admin/tenants/${id}/feature-flags`, { enabled_flags }),
  getTenantRealEstatePack: (id: string) =>
    api.get(`/admin/tenants/${id}/real-estate-pack`),
  getLaunchBoard: (params?: { search?: string; stage?: string; limit?: number }) =>
    api.get('/admin/launch-board', { params }),
  updateLaunchConcierge: (tenantId: string, data: {
    status: 'pending' | 'in_progress' | 'ready_for_review' | 'launched' | 'blocked'
    note?: string
    create_ticket?: boolean
  }) => api.patch(`/admin/launch-board/${tenantId}/concierge`, data),
  updateTenantBusinessProfile: (tenantId: string, data: {
    industry: string
    tone: string
    summary: string
    services: string[]
    faq?: Array<Record<string, unknown>>
    status: 'customer_collected' | 'admin_enriched' | 'ready'
  }) => api.patch(`/admin/tenants/${tenantId}/business-profile`, data),
  runTenantAutopilot: (tenantId: string) => api.post(`/admin/tenants/${tenantId}/autopilot/run`),
  runTenantVerification: (tenantId: string) => api.post(`/admin/tenants/${tenantId}/verification/run`),
  launchTenant: (tenantId: string) => api.post(`/admin/tenants/${tenantId}/launch`),
  updateTenantRealEstatePack: (id: string, data: {
    enabled: boolean
    lead_limit_monthly: number
    pdf_limit_monthly: number
    followup_limit_monthly: number
  }) => api.put(`/admin/tenants/${id}/real-estate-pack`, data),
  suspendTenant: (id: string) => api.post(`/admin/tenants/${id}/suspend`),
  unsuspendTenant: (id: string) => api.post(`/admin/tenants/${id}/unsuspend`),
  deleteTenant: (id: string) => api.delete(`/admin/tenants/${id}`),
  listSalesInquiries: (params?: { status?: string; search?: string; limit?: number }) =>
    api.get('/admin/sales-inquiries', { params }),
  updateSalesInquiry: (id: string, status: 'new' | 'contacted' | 'qualified' | 'closed' | 'spam') =>
    api.patch(`/admin/sales-inquiries/${id}`, { status }),
  listInvoices: (params?: { search?: string; status?: 'draft' | 'sent' | 'paid' | 'cancelled'; limit?: number }) =>
    api.get('/admin/invoices', { params }),
  getInvoice: (id: string) => api.get(`/admin/invoices/${id}`),
  createInvoice: (data: Record<string, unknown>) => api.post('/admin/invoices', data),
  updateInvoiceStatus: (id: string, status: 'draft' | 'sent' | 'paid' | 'cancelled') =>
    api.patch(`/admin/invoices/${id}/status`, { status }),
  updateTenantPlan: (id: string, data: {
    plan_type: 'free' | 'pro' | 'premium' | 'enterprise'
    note: string
  }) => api.put(`/admin/tenants/${id}/plan`, data),

  // Plans
  listPlans: (params?: { page?: number; page_size?: number; search?: string; is_active?: boolean; is_public?: boolean }) =>
    api.get('/admin/plans', { params }),
  createPlan: (data: {
    name: string
    display_name: string
    description?: string
    plan_type: string
    price_monthly: number
    price_yearly: number
    currency: string
    message_limit: number
    bot_limit: number
    knowledge_items_limit: number
    feature_flags: Record<string, unknown>
    trial_days: number
    is_active: boolean
    is_public: boolean
    sort_order: number
  }) => api.post('/admin/plans', data),
  updatePlan: (id: string, data: Partial<{
    name: string
    display_name: string
    description: string
    plan_type: string
    price_monthly: number
    price_yearly: number
    currency: string
    message_limit: number
    bot_limit: number
    knowledge_items_limit: number
    feature_flags: Record<string, unknown>
    trial_days: number
    is_active: boolean
    is_public: boolean
    sort_order: number
  }>) => api.put(`/admin/plans/${id}`, data),
  deletePlan: (id: string) => api.delete(`/admin/plans/${id}`),

  // Tools
  listTools: (params?: { page?: number; page_size?: number; search?: string; category?: string; status?: string; coming_soon?: boolean }) =>
    api.get('/admin/tools', { params }),
  createTool: (data: {
    key: string
    name: string
    description?: string
    category?: string
    icon?: string
    tags?: string[]
    required_plan?: string
    status: string
    is_public: boolean
    coming_soon: boolean
  }) => api.post('/admin/tools', data),
  updateTool: (id: string, data: Partial<{
    key: string
    name: string
    description: string
    category: string
    icon: string
    tags: string[]
    required_plan: string
    status: string
    is_public: boolean
    coming_soon: boolean
  }>) => api.put(`/admin/tools/${id}`, data),
  deleteTool: (id: string) => api.delete(`/admin/tools/${id}`),

  // Audit logs
  listAuditLogs: (params?: { skip?: number; limit?: number; tenant_id?: string; action?: string }) =>
    api.get('/admin/audit', { params }),
  
  // System
  getHealth: () => api.get('/admin/health'),
}

// Onboarding API (WhatsApp)
export const onboardingApi = {
  // WhatsApp Onboarding
  startWhatsApp: () => api.post('/api/onboarding/whatsapp/start'),
  startOpenWA: (acceptedUnofficialRisk: boolean) =>
    api.post('/api/onboarding/whatsapp/openwa/start', {
      accepted_unofficial_risk: acceptedUnofficialRisk,
    }),
  getOpenWAQr: () => api.get('/api/onboarding/whatsapp/openwa/qr'),
  reconnectOpenWA: () => api.post('/api/onboarding/whatsapp/openwa/reconnect'),
  refreshOpenWAQr: () => api.post('/api/onboarding/whatsapp/openwa/qr/refresh'),
  disconnectOpenWA: () => api.post('/api/onboarding/whatsapp/openwa/disconnect'),
  getWhatsAppStatus: () => api.get('/api/onboarding/whatsapp/status'),
  getWhatsAppAccount: () => api.get('/api/onboarding/whatsapp/account'),
  resetWhatsApp: () => api.post('/api/onboarding/whatsapp/reset'),
  retryStep: (stepKey: string) => api.post(`/api/onboarding/whatsapp/retry-step/${stepKey}`),
}

// Subscription API
export const subscriptionApi = {
  listPlans: () => api.get('/subscription/plans'),
  getCurrentSubscription: () => api.get('/subscription/current'),
  getUsageStats: () => api.get('/subscription/usage'),
  upgrade: (planName: string) => api.post('/subscription/upgrade', { plan_name: planName }),
  cancel: (immediate: boolean = false) => api.post('/subscription/cancel', null, { params: { immediate } }),
  checkFeature: (featureKey: string) => api.get(`/subscription/check-feature/${featureKey}`),
}

// Payments API
export const paymentsApi = {
  createCheckout: (data: { plan_name: string; interval?: 'monthly' | 'yearly' }) =>
    api.post('/payments/checkout', data),
}

export const billingApi = {
  getConfig: () => api.get('/billing/config'),
  getPlan: () => api.get('/billing/plan'),
  getLimits: () => api.get('/billing/limits'),
  createManualPlanRequest: (data: {
    plan: 'pro' | 'premium' | 'enterprise'
    interval?: 'monthly' | 'yearly'
    note?: string
  }) => api.post('/billing/manual-request', data),
  createStripeCheckoutSession: (data: { plan: 'pro' | 'premium'; interval?: 'monthly' | 'yearly' }) =>
    api.post('/billing/stripe/checkout-session', data),
  createStripePortalSession: (params?: { return_url?: string }) =>
    api.get('/billing/stripe/portal', { params }),
}

export const contactApi = {
  createInquiry: (data: {
    name: string
    email: string
    company?: string
    phone?: string
    plan?: string
    interval?: string
    message: string
    website?: string
  }) => api.post('/public/contact', data),
}

// Tenant Onboarding API (Setup Wizard)
export const setupOnboardingApi = {
  getStatus: () => api.get('/onboarding/setup/status'),
  completeStep: (stepKey: string) => api.post('/onboarding/setup/complete-step', { step_key: stepKey }),
  saveBusinessProfile: (data: {
    industry: string
    primary_goal: string
    tone: string
    handoff_rules: string[]
    website_url?: string
    instagram_url?: string
    business_summary?: string
  }) => api.post('/onboarding/setup/business-profile', data),
  runAutopilot: () => api.post('/onboarding/setup/run-autopilot'),
  dismiss: () => api.post('/onboarding/setup/dismiss'),
  checkProgress: () => api.post('/onboarding/setup/check-progress'),
  getNextAction: () => api.get('/onboarding/setup/next-action'),
}

// Analytics API
export const analyticsApi = {
  getDashboardStats: () => api.get('/analytics/dashboard'),
  getChartData: (days: number = 30) => api.get('/analytics/chart-data', { params: { days } }),
  getBotStats: (botId: string) => api.get(`/analytics/bot/${botId}`),
  getSourceBreakdown: () => api.get('/analytics/sources'),
  getUsageSummary: () => api.get('/analytics/usage-summary'),
  getOperationalReport: (period: 'today' | 'week' = 'today') =>
    api.get('/analytics/operational-report', { params: { period } }),
  getCustomerSuccess: (days: number = 30) => api.get('/analytics/customer-success', { params: { days } }),
  getActionCenter: (windowHours: number = 24) =>
    api.get('/analytics/action-center', { params: { window_hours: windowHours } }),
}

export const productAnalyticsApi = {
  getFriction: (days: number = 30) => api.get('/product-analytics/friction', { params: { days } }),
  getGlobalFriction: (days: number = 30) => api.get('/admin/product-analytics/friction', { params: { days } }),
}

export type DataRetentionPolicy = {
  tenant_id: string
  enabled: boolean
  legal_hold: boolean
  message_content_days: number
  raw_payload_days: number
  product_analytics_days: number
  usage_log_days: number
  system_event_days: number
  media_days: number
  call_data_days: number
  ticket_days: number
  artifact_days: number
  last_run_at?: string | null
  last_result: Record<string, number>
  updated_at: string
}

export const dataRetentionApi = {
  get: () => api.get<DataRetentionPolicy>('/data-retention'),
  preview: () => api.get('/data-retention/preview'),
  update: (data: Omit<DataRetentionPolicy, 'tenant_id' | 'legal_hold' | 'last_run_at' | 'last_result' | 'updated_at'>) =>
    api.patch<DataRetentionPolicy>('/data-retention', data),
  run: () => api.post('/data-retention/run'),
}

// Operator API
export const operatorApi = {
  listConversations: (statusFilter?: string) => 
    api.get('/operator/conversations', { params: { status_filter: statusFilter } }),
  takeoverConversation: (conversationId: string) => 
    api.post('/operator/takeover', { conversation_id: conversationId }),
  releaseConversation: (conversationId: string) => 
    api.post('/operator/release', { conversation_id: conversationId }),
  sendMessage: (conversationId: string, content: string) => 
    api.post('/operator/send-message', { conversation_id: conversationId, content }),
  getConversationMessages: (conversationId: string, skip?: number, limit?: number) =>
    api.get(`/operator/conversation/${conversationId}/messages`, { params: { skip, limit } }),
}

// Appointments API
export const appointmentsApi = {
  list: (params?: { status?: string }) => api.get('/appointments', { params }),
  getSettings: () => api.get('/appointments/settings'),
  updateSettings: (data: AppointmentSettings) => api.patch('/appointments/settings', data),
  getAvailability: (params?: { start_date?: string; days?: number; service_id?: string }) =>
    api.get('/appointments/availability', { params }),
  create: (data: {
    customer_name: string
    customer_email?: string
    customer_phone?: string
    subject: string
    starts_at: string
    duration_minutes?: number
    notes?: string
    reminder_before_minutes?: number
  }) => api.post('/appointments', data),
  update: (id: string, data: Partial<{
    customer_name: string
    customer_email: string
    customer_phone: string
    subject: string
    starts_at: string
    duration_minutes: number
    notes: string
    status: 'scheduled' | 'completed' | 'cancelled'
    reminder_before_minutes: number
  }>) => api.patch(`/appointments/${id}`, data),
  sendReminders: () => api.post('/appointments/send-reminders'),
}

export interface AppointmentService {
  id: string
  name: string
  duration_minutes: number
  active: boolean
}

export interface BusinessHoursDay {
  enabled: boolean
  start: string
  end: string
}

export interface AppointmentSettings {
  configured: boolean
  timezone: string
  minimum_notice_hours: number
  booking_window_days: number
  slot_interval_minutes: number
  booking_location: string
  booking_notes: string
  services: AppointmentService[]
  weekly_hours: Record<string, BusinessHoursDay>
  closed_dates: string[]
}

export interface AppointmentAvailability {
  timezone: string
  reliable: boolean
  calendar_connected: boolean
  warnings: string[]
  slots: Array<{
    start_at: string
    end_at: string
    local_label: string
    service_id: string
    service_name: string
    duration_minutes: number
  }>
}

// Notes API
export const notesApi = {
  list: (params?: { archived?: boolean }) => api.get('/notes', { params }),
  create: (data: {
    title: string
    content: string
    color?: string
    pinned?: boolean
    position_x?: number
    position_y?: number
  }) => api.post('/notes', data),
  update: (id: string, data: Partial<{
    title: string
    content: string
    color: string
    pinned: boolean
    position_x: number
    position_y: number
    archived: boolean
  }>) => api.patch(`/notes/${id}`, data),
  delete: (id: string) => api.delete(`/notes/${id}`),
}

// Tenant API Keys
export const apiKeysApi = {
  list: (params?: { include_revoked?: boolean }) => api.get('/api-keys', { params }),
  create: (data: { name: string; current_password: string }) => api.post('/api-keys', data),
  revoke: (id: string, data: { current_password: string }) => api.delete(`/api-keys/${id}`, { data }),
}

// Real Estate Pack API
export const realEstateApi = {
  getSettings: () => api.get('/real-estate/settings'),
  updateSettings: (data: Partial<{
    enabled: boolean
    persona: 'luxury' | 'pro' | 'warm'
    lead_limit_monthly: number
    pdf_limit_monthly: number
    followup_limit_monthly: number
    followup_days: number
    followup_attempts: number
    question_flow_buyer: Record<string, unknown>
    question_flow_seller: Record<string, unknown>
    listings_source: Record<string, unknown>
    manual_availability: unknown[]
    google_calendar_enabled: boolean
    google_calendar_email: string
    report_logo_url: string
    report_brand_color: string
    report_footer: string
  }>) => api.put('/real-estate/settings', data),
  listListings: (params?: { search?: string; sale_rent?: 'sale' | 'rent'; active_only?: boolean }) =>
    api.get('/real-estate/listings', { params }),
  createListing: (data: {
    title: string
    description?: string
    sale_rent: 'sale' | 'rent'
    property_type: string
    location_text: string
    lat?: number
    lng?: number
    price: number
    currency?: string
    m2?: number
    rooms?: string
    features?: Record<string, unknown>
    media?: unknown[]
    url?: string
    is_active?: boolean
  }) => api.post('/real-estate/listings', data),
  updateListing: (id: string, data: Partial<{
    title: string
    description: string
    sale_rent: 'sale' | 'rent'
    property_type: string
    location_text: string
    lat: number
    lng: number
    price: number
    currency: string
    m2: number
    rooms: string
    features: Record<string, unknown>
    media: unknown[]
    url: string
    is_active: boolean
  }>) => api.patch(`/real-estate/listings/${id}`, data),
  deleteListing: (id: string) => api.delete(`/real-estate/listings/${id}`),
  importListingsCsv: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/real-estate/listings/import/csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  syncListingsFromGoogleSheets: (data: {
    sheet_url?: string
    gid?: string
    csv_url?: string
    mapping?: Record<string, string>
    deactivate_missing?: boolean
    save_to_settings?: boolean
  }) => api.post('/real-estate/listings/sync/google-sheets', data),
  syncListingsFromRemax: (data: {
    endpoint_url?: string
    response_path?: string
    auth_header?: string
    auth_scheme?: string
    api_key?: string
    mapping?: Record<string, string>
    deactivate_missing?: boolean
    save_to_settings?: boolean
  }) => api.post('/real-estate/listings/sync/remax', data),
  listTemplates: () => api.get('/real-estate/templates'),
  createTemplate: (data: {
    name: string
    category: string
    language?: string
    meta_template_id?: string
    variables_schema?: Record<string, unknown>
    status?: string
    content_preview?: string
    is_approved?: boolean
  }) => api.post('/real-estate/templates', data),
  updateTemplate: (id: string, data: Partial<{
    name: string
    category: string
    language: string
    meta_template_id: string
    variables_schema: Record<string, unknown>
    status: string
    content_preview: string
    is_approved: boolean
  }>) => api.patch(`/real-estate/templates/${id}`, data),
  suggestListingsForLead: (leadId: string) => api.post(`/real-estate/leads/${leadId}/suggest-listings`),
  bookAppointment: (data: {
    lead_id: string
    agent_id?: string
    listing_id?: string
    start_at: string
    end_at?: string
    meeting_mode?: string
    notes?: string
  }) => api.post('/real-estate/appointments/book', data),
  getAvailableSlots: (params: {
    agent_id: string
    start_at: string
    end_at: string
    duration_minutes?: number
    step_minutes?: number
  }) => api.get('/real-estate/appointments/available-slots', { params }),
  runFollowups: () => api.post('/real-estate/followups/run'),
  getWeeklyAnalytics: () => api.get('/real-estate/analytics/weekly'),
  listAgents: () => api.get('/real-estate/agents'),
  getAiSuggestedListings: (leadId: string, params?: { limit?: number }) =>
    api.get(`/real-estate/leads/${leadId}/ai-suggested-listings`, { params }),
  recordListingEvent: (leadId: string, data: {
    listing_id: string
    event: 'sent' | 'clicked' | 'saved' | 'ignored' | 'viewed' | 'offer'
    meta_json?: Record<string, unknown>
  }) => api.post(`/real-estate/leads/${leadId}/listing-events`, data),
  startGoogleCalendarOAuth: (params?: { agent_id?: string }) =>
    api.get('/real-estate/calendar/google/start', { params }),
  getGoogleCalendarStatus: (params?: { agent_id?: string }) =>
    api.get('/real-estate/calendar/google/status', { params }),
  getGoogleCalendarDiagnostics: (params?: { live?: boolean }) =>
    api.get('/real-estate/calendar/google/diagnostics', { params }),
  disconnectGoogleCalendar: (params?: { agent_id?: string }) =>
    api.delete('/real-estate/calendar/google/disconnect', { params }),
  generateListingSummaryPdf: (data: {
    listing_ids: string[]
    lead_id?: string
    send_whatsapp?: boolean
  }) => api.post('/real-estate/pdf/generate', data),
  downloadListingSummaryPdf: (data: {
    listing_ids: string[]
    lead_id?: string
  }) => api.post('/real-estate/pdf/download', data, { responseType: 'blob' }),
  sendSellerServiceReport: (leadId: string) => api.post(`/real-estate/leads/${leadId}/seller-service-report`),
  sendWeeklyReportNow: () => api.post('/real-estate/reports/weekly/send'),
  downloadWeeklyReport: (week_start: string) =>
    api.get('/real-estate/reports/weekly/download', { params: { week_start }, responseType: 'blob' }),
}

// Automation API (n8n Integration)
export const automationApi = {
  // Settings
  getSettings: () => api.get('/automation/settings'),
  updateSettings: (data: {
    use_n8n?: boolean
    default_workflow_id?: string
    whatsapp_workflow_id?: string
    widget_workflow_id?: string
    call_workflow_id?: string
    custom_n8n_url?: string
    enable_auto_retry?: boolean
    max_retries?: number
    timeout_seconds?: number
  }) => api.put('/automation/settings', data),
  
  // Status
  getStatus: () => api.get('/automation/status'),
  
  // Runs
  listRuns: (params?: { skip?: number; limit?: number; status_filter?: string }) =>
    api.get('/automation/runs', { params }),
  
  // Test
  sendTestEvent: (testMessage?: string) =>
    api.post('/automation/test', { test_message: testMessage || 'Test message' }),
}

// Tool Marketplace API
export const toolMarketplaceApi = {
  listTools: () => api.get('/tools'),
  updateToolSettings: (
    slug: string,
    data: { enabled: boolean; rateLimitPerMinute?: number | null; config?: Record<string, unknown> }
  ) => api.put(`/tools/${slug}/settings`, data),
  runTool: (data: {
    requestId?: string
    toolSlug: string
    toolInput: Record<string, unknown>
    context?: {
      locale?: string
      timezone?: string
      channel?: string
      memory?: Record<string, unknown>
    }
  }) => api.post('/tools/run', data),
  listRuns: (params?: { limit?: number; offset?: number }) => api.get('/tools/runs', { params }),
  getRun: (requestId: string) => api.get(`/tools/runs/${requestId}`),
}

// Integrations API
export const integrationsApi = {
  getStatus: () => api.get('/integrations/status'),
  getDiagnostics: () => api.get('/integrations/diagnostics'),
  repair: (provider: string) => api.post(`/integrations/${provider}/repair`),
  startGoogleOAuth: () => api.get('/integrations/google/start'),
}

export const notificationsApi = {
  getSettings: () => api.get('/notifications/settings'),
  subscribe: (subscription: PushSubscriptionJSON) =>
    api.post('/notifications/subscribe', subscription),
  updateSettings: (data: {
    notify_ai_reply: boolean
    notify_new_lead: boolean
    notify_appointment: boolean
    notify_weekly_report: boolean
  }) => api.patch('/notifications/settings', data),
  unsubscribe: (endpoint?: string) =>
    api.delete('/notifications/subscribe', { data: { endpoint } }),
}

export const autopilotApi = {
  getStatus: () => api.get('/setup/autopilot/status'),
  run: () => api.post('/setup/autopilot/run'),
  verify: () => api.post('/setup/autopilot/verify'),
}

export const agencyApi = {
  listClients: () => api.get('/agency/clients'),
  createClient: (data: { client_tenant_id: string; notes?: string }) => api.post('/agency/clients', data),
  getClientHealth: (tenantId: string) => api.get(`/agency/clients/${tenantId}/health`),
  updateClient: (relationshipId: string, data: { status?: 'active' | 'paused' | 'archived'; notes?: string }) =>
    api.patch(`/agency/clients/${relationshipId}`, data),
  archiveClient: (relationshipId: string) => api.delete(`/agency/clients/${relationshipId}`),
}

// System Events API
export const systemEventsApi = {
  list: (params?: { skip?: number; limit?: number; level?: string; source?: string; code?: string; tenant_id?: string }) =>
    api.get('/system-events', { params }),
}

// Incidents API
export const incidentsApi = {
  list: (params?: { skip?: number; limit?: number; status?: string; severity?: string }) =>
    api.get('/incidents', { params }),
  get: (id: string) => api.get(`/incidents/${id}`),
  create: (data: { title: string; severity: string; status: string; tenant_id?: string | null }) =>
    api.post('/incidents', data),
  update: (id: string, data: Partial<{ title: string; severity: string; status: string; assigned_to?: string | null; root_cause?: string | null; resolution?: string | null }>) =>
    api.patch(`/incidents/${id}`, data),
}

// Tickets API
export const ticketsApi = {
  list: (params?: { skip?: number; limit?: number; status?: string; priority?: string; tenant_id?: string }) =>
    api.get('/tickets', { params }),
  get: (id: string) => api.get(`/tickets/${id}`),
  create: (data: { subject: string; priority: string; message: string }) =>
    api.post('/tickets', data),
  createPrivacyRequest: (data: { request_type: 'export' | 'deletion' | 'correction'; consent_ack: boolean; note?: string }) =>
    api.post('/tickets/privacy-requests', data),
  addMessage: (id: string, data: { body: string }) =>
    api.post(`/tickets/${id}/messages`, data),
  update: (id: string, data: Partial<{ status: string; priority: string; assigned_to?: string | null }>) =>
    api.patch(`/tickets/${id}`, data),
}
