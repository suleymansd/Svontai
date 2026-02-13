import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { clearAdminTenantContext } from './admin-tenant-context'
import type { ToolWorkspaceConfig } from '@/components/tools/types'

interface User {
  id: string
  email: string
  full_name: string
  is_admin?: boolean
}

interface Tenant {
  id: string
  name: string
}

interface Role {
  id: string
  name: string
  description?: string | null
}

interface AuthState {
  user: User | null
  tenant: Tenant | null
  role: Role | null
  permissions: string[]
  entitlements: Record<string, any>
  featureFlags: Record<string, boolean>
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  setTenant: (tenant: Tenant | null) => void
  setRole: (role: Role | null) => void
  setPermissions: (permissions: string[]) => void
  setEntitlements: (entitlements: Record<string, any>) => void
  setFeatureFlags: (flags: Record<string, boolean>) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      tenant: null,
      role: null,
      permissions: [],
      entitlements: {},
      featureFlags: {},
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setTenant: (tenant) => set({ tenant }),
      setRole: (role) => set({ role }),
      setPermissions: (permissions) => set({ permissions }),
      setEntitlements: (entitlements) => set({ entitlements }),
      setFeatureFlags: (flags) => set({ featureFlags: flags }),
      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        clearAdminTenantContext()
        set({
          user: null,
          tenant: null,
          role: null,
          permissions: [],
          entitlements: {},
          featureFlags: {},
          isAuthenticated: false
        })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        tenant: state.tenant,
        role: state.role,
        permissions: state.permissions,
        entitlements: state.entitlements,
        featureFlags: state.featureFlags,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

interface UIState {
  sidebarOpen: boolean
  theme: 'light' | 'dark' | 'system'
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void
  setTheme: (theme: 'light' | 'dark' | 'system') => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      theme: 'system',
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: 'ui-storage',
    }
  )
)

interface ToolState {
  installedToolIds: string[]
  toolConfigs: Record<string, ToolWorkspaceConfig>
  installTool: (toolId: string) => void
  uninstallTool: (toolId: string) => void
  setToolConfig: (toolId: string, config: ToolWorkspaceConfig) => void
  resetTools: () => void
}

export const useToolStore = create<ToolState>()(
  persist(
    (set) => ({
      installedToolIds: [],
      toolConfigs: {},
      installTool: (toolId) =>
        set((state) => ({
          installedToolIds: state.installedToolIds.includes(toolId)
            ? state.installedToolIds
            : [...state.installedToolIds, toolId],
        })),
      uninstallTool: (toolId) =>
        set((state) => ({
          installedToolIds: state.installedToolIds.filter((id) => id !== toolId),
        })),
      setToolConfig: (toolId, config) =>
        set((state) => ({
          toolConfigs: {
            ...state.toolConfigs,
            [toolId]: config,
          },
        })),
      resetTools: () => set({ installedToolIds: [], toolConfigs: {} }),
    }),
    {
      name: 'tool-storage',
    }
  )
)
