import type { ComponentType } from 'react'
import {
  Bot,
  Brain,
  CalendarCheck,
  Contact,
  CreditCard,
  NotebookPen,
  Smile,
} from 'lucide-react'
import type { Tool, ToolWorkspaceConfig } from './types'

export interface ToolCatalogItem {
  id: string
  name: string
  category: string
  description: string
  icon: string
  tags: string[]
  menuIcon: ComponentType<{ className?: string }>
  accent: {
    from: string
    to: string
  }
}

export const TOOL_CATALOG: ToolCatalogItem[] = [
  {
    id: 'tool-whatsapp-crm',
    name: 'WhatsApp CRM',
    category: 'CRM',
    description: 'WhatsApp mesajlarını otomatik müşteri profiline dönüştürür.',
    icon: 'WA',
    tags: ['WhatsApp', 'CRM'],
    menuIcon: Contact,
    accent: { from: 'from-emerald-500', to: 'to-teal-500' },
  },
  {
    id: 'tool-ai-reply',
    name: 'AI Yanıt',
    category: 'AI',
    description: 'Gelen mesajlara akıllı cevap önerileri üretir.',
    icon: 'AI',
    tags: ['AI', 'Support'],
    menuIcon: Brain,
    accent: { from: 'from-violet-500', to: 'to-fuchsia-500' },
  },
  {
    id: 'tool-appointment',
    name: 'Randevu Planlayıcı',
    category: 'Scheduling',
    description: 'Müşteriler için otomatik randevu akışı başlatır.',
    icon: 'RP',
    tags: ['Takvim', 'CRM'],
    menuIcon: CalendarCheck,
    accent: { from: 'from-sky-500', to: 'to-indigo-500' },
  },
  {
    id: 'tool-lead-collector',
    name: 'Lead Toplayıcı',
    category: 'Growth',
    description: 'Potansiyel müşteri verilerini etiketleyip saklar.',
    icon: 'LT',
    tags: ['Lead', 'Form'],
    menuIcon: Bot,
    accent: { from: 'from-amber-500', to: 'to-orange-500' },
  },
  {
    id: 'tool-billing',
    name: 'Ödeme Hatırlatıcı',
    category: 'Finance',
    description: 'Geciken ödemeler için otomatik bildirim gönderir.',
    icon: 'ÖH',
    tags: ['Finans', 'Otomasyon'],
    menuIcon: CreditCard,
    accent: { from: 'from-blue-500', to: 'to-cyan-500' },
  },
  {
    id: 'tool-feedback',
    name: 'Memnuniyet Ölçer',
    category: 'Support',
    description: 'Müşteri geri bildirimi toplayıp raporlar.',
    icon: 'MO',
    tags: ['CSAT', 'Support'],
    menuIcon: Smile,
    accent: { from: 'from-rose-500', to: 'to-pink-500' },
  },
  {
    id: 'tool-note',
    name: 'Not Tool',
    category: 'Productivity',
    description: 'Ekip içi notları, görev notlarını ve müşteri notlarını yönetir.',
    icon: 'NT',
    tags: ['Not', 'İç Operasyon'],
    menuIcon: NotebookPen,
    accent: { from: 'from-slate-600', to: 'to-zinc-500' },
  },
]

export const TOOL_CATALOG_MAP: Record<string, ToolCatalogItem> = Object.fromEntries(
  TOOL_CATALOG.map((tool) => [tool.id, tool])
)

export function getToolCatalogItem(toolId: string): ToolCatalogItem | undefined {
  return TOOL_CATALOG_MAP[toolId]
}

export function createDefaultToolWorkspaceConfig(tool: Pick<Tool, 'name' | 'category' | 'description' | 'tags'>): ToolWorkspaceConfig {
  return {
    customization: {
      name: tool.name,
      category: tool.category,
      description: tool.description,
      tags: tool.tags ?? [],
    },
    integration: {
      provider: '',
      apiKey: '',
      baseUrl: '',
      webhookUrl: '',
      enabled: false,
      autoSync: true,
    },
    internal: {
      owner: '',
      environment: 'test',
      notes: '',
      runbook: '',
    },
  }
}
