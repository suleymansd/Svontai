import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// Handle token refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          const response = await axios.post(`${API_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })

          const { access_token } = response.data
          localStorage.setItem('access_token', access_token)

          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      }
    }

    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api.post('/auth/register', data),
  
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  
  refresh: (refresh_token: string) =>
    api.post('/auth/refresh', { refresh_token }),
}

// User API
export const userApi = {
  getMe: () => api.get('/me'),
  updateMe: (data: { full_name?: string; email?: string }) =>
    api.put('/me', data),
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
  get: (id: string) => api.get(`/bots/${id}`),
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
  deleteTenant: (id: string) => api.delete(`/admin/tenants/${id}`),
  
  // System
  getHealth: () => api.get('/admin/health'),
}

// Onboarding API (WhatsApp)
export const onboardingApi = {
  // WhatsApp Onboarding
  startWhatsApp: () => api.post('/api/onboarding/whatsapp/start'),
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

// Tenant Onboarding API (Setup Wizard)
export const setupOnboardingApi = {
  getStatus: () => api.get('/onboarding/setup/status'),
  completeStep: (stepKey: string) => api.post('/onboarding/setup/complete-step', { step_key: stepKey }),
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
