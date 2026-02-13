import type { ComponentType } from 'react'
import { Boxes } from 'lucide-react'
import { getToolCatalogItem } from './catalog'
import type { ToolWorkspaceConfig } from './types'

export interface ToolMenuItem {
  id: string
  name: string
  href: string
  icon: ComponentType<{ className?: string }>
}

export function getToolMenuItems(
  installedToolIds: string[],
  toolConfigs: Record<string, ToolWorkspaceConfig> = {}
): ToolMenuItem[] {
  return installedToolIds
    .map((toolId) => {
      const catalogItem = getToolCatalogItem(toolId)
      if (!catalogItem) return null

      const customizedName = toolConfigs[toolId]?.customization?.name?.trim()

      return {
        id: toolId,
        name: customizedName || catalogItem.name,
        href: `/panel/tools/${toolId}`,
        icon: catalogItem.menuIcon ?? Boxes,
      }
    })
    .filter((item): item is ToolMenuItem => item !== null)
}
