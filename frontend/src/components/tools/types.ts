export type ToolStatus = 'idle' | 'added'

export interface Tool {
  id: string
  name: string
  category: string
  status: ToolStatus
  description: string
  icon: string
  tags?: string[]
}

export interface ToolWorkspaceConfig {
  customization: {
    name: string
    category: string
    description: string
    tags: string[]
  }
  integration: {
    provider: string
    apiKey: string
    baseUrl: string
    webhookUrl: string
    enabled: boolean
    autoSync: boolean
  }
  internal: {
    owner: string
    environment: 'test' | 'prod'
    notes: string
    runbook: string
  }
}
