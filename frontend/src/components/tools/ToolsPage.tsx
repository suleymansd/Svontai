'use client'

import type { DragEvent } from 'react'
import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Boxes, LayoutGrid, PlayCircle } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ToolCard } from '@/components/tools/ToolCard'
import { ToolDropZone } from '@/components/tools/ToolDropZone'
import { ToolGuideOverlay } from '@/components/tools/ToolGuideOverlay'
import { TOOL_CATALOG, createDefaultToolWorkspaceConfig, getToolCatalogItem } from '@/components/tools/catalog'
import type { Tool } from '@/components/tools/types'
import { useToolStore } from '@/lib/store'

export function ToolsPage() {
  const router = useRouter()
  const { installedToolIds, toolConfigs, installTool, setToolConfig } = useToolStore()
  const [guideOpen, setGuideOpen] = useState(false)

  const tools = useMemo<Tool[]>(
    () =>
      TOOL_CATALOG.map((catalogTool) => {
        const customization = toolConfigs[catalogTool.id]?.customization

        return {
          id: catalogTool.id,
          name: customization?.name?.trim() || catalogTool.name,
          category: customization?.category?.trim() || catalogTool.category,
          status: installedToolIds.includes(catalogTool.id) ? 'added' : 'idle',
          description: customization?.description?.trim() || catalogTool.description,
          icon: catalogTool.icon,
          tags: customization ? customization.tags : catalogTool.tags,
        }
      }),
    [installedToolIds, toolConfigs]
  )

  const addedTools = useMemo(() => tools.filter((tool) => tool.status === 'added'), [tools])

  const handleDragStart = (tool: Tool, event: DragEvent<HTMLDivElement>) => {
    event.dataTransfer.setData('text/plain', tool.id)
    event.dataTransfer.effectAllowed = 'move'
  }

  const activateTool = (toolId: string) => {
    const catalogTool = getToolCatalogItem(toolId)
    if (!catalogTool) return

    if (!toolConfigs[toolId]) {
      setToolConfig(toolId, createDefaultToolWorkspaceConfig(catalogTool))
    }
    installTool(toolId)
    router.push(`/dashboard/tools/${toolId}`)
  }

  const handleDropTool = (toolId: string) => {
    activateTool(toolId)
  }

  const handleCardClick = (tool: Tool) => {
    activateTool(tool.id)
  }

  return (
    <ContentContainer>
      <div className="relative">
        <ToolGuideOverlay open={guideOpen} onClose={() => setGuideOpen(false)} />

        <div className="space-y-8">
          <PageHeader
            title="Tool Kataloğu"
            description="SvontAI iş akışınıza ekleyebileceğiniz tool’ları yönetin."
            icon={<Icon3DBadge icon={Boxes} size="md" from="from-primary" to="to-violet-500" />}
            actions={(
              <Button variant="outline" onClick={() => setGuideOpen(true)}>
                <PlayCircle className="mr-2 h-4 w-4" />
                Rehberi Başlat
              </Button>
            )}
          />

          <div className="grid gap-6 lg:grid-cols-[1.2fr,0.8fr]">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <LayoutGrid className="h-4 w-4 text-muted-foreground" />
                Tüm Tool’lar
              </div>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {tools.map((tool) => (
                  <ToolCard
                    key={tool.id}
                    tool={tool}
                    onClick={handleCardClick}
                    onDragStart={handleDragStart}
                  />
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <ToolDropZone tools={addedTools} onDropTool={handleDropTool} />
              <Card>
                <CardContent className="space-y-2 p-4 text-sm text-muted-foreground">
                  <p className="font-semibold text-foreground">Workflow ipuçları</p>
                  <p>Tool’ları sürükleyerek aktif workflow’a ekleyin ve ayar ekranından yapılandırın.</p>
                  <p>Eklenen tool’lar otomatik olarak önerilen şablonlarla gelir.</p>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>

      </div>
    </ContentContainer>
  )
}
