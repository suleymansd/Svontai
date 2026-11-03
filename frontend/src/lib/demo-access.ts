import axios from 'axios'
import { api } from './api'

export interface DemoAccess {
  id: string
  name: string
  tenant_id: string
  created_at: string
  expires_at: string
  last_used_at: string | null
  revoked_at: string | null
  visit_count: number
  status: 'active' | 'expired' | 'revoked'
}

export interface DemoLink extends DemoAccess { url: string }

export const demoAccessApi = {
  list: () => api.get<DemoAccess[]>('/admin/demo-access'),
  create: (name: string, days: number) => api.post<DemoLink>('/admin/demo-access', { name, days }),
  rotate: (id: string) => api.post<DemoLink>(`/admin/demo-access/${id}/rotate`),
  revoke: (id: string) => api.delete(`/admin/demo-access/${id}`),
  enter: (token: string) => axios.post<{ access_token: string }>('/api/auth/demo-login', { token }, { withCredentials: true }),
}
