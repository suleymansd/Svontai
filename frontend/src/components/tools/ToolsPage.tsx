'use client'

import type { DragEvent } from 'react'
import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { LayoutGrid, PlayCircle } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ToolCard } from '@/components/tools/ToolCard'
import { ToolDropZone } from '@/components/tools/ToolDropZone'
import { ToolDetailModal } from '@/components/tools/ToolDetailModal'
import { ToolGuideOverlay } from '@/components/tools/ToolGuideOverlay'
import { TOOL_CATALOG, createDefaultToolWorkspaceConfig, getToolCatalogItem } from '@/components/tools/catalog'
import type { Tool } from '@/components/tools/types'
import { useToolStore } from '@/lib/store'

export function ToolsPage() {
  const router = useRouter()
  const { installedToolIds, toolConfigs, installTool, setToolConfig } = useToolStore()
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
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

  const selectedTool = useMemo(
    () => tools.find((tool) => tool.id === selectedToolId) ?? null,
    [tools, selectedToolId]
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
    router.push(`/panel/tools/${toolId}`)
  }

  const handleDropTool = (toolId: string) => {
    activateTool(toolId)
  }

  const handleCardClick = (tool: Tool) => {
    setSelectedToolId(tool.id)
    setModalOpen(true)
    setGuideOpen(true)
  }

  const handleModalChange = (open: boolean) => {
    setModalOpen(open)
    if (!open) setGuideOpen(false)
  }

  const handleAddToWorkflow = (toolId: string) => {
    activateTool(toolId)
    setModalOpen(false)
    setGuideOpen(false)
  }

  const handleSaveTool = (toolId: string, updates: Partial<Tool>) => {
    const catalogTool = getToolCatalogItem(toolId)
    if (!catalogTool) return

    const currentConfig = toolConfigs[toolId] ?? createDefaultToolWorkspaceConfig(catalogTool)
    setToolConfig(toolId, {
      ...currentConfig,
      customization: {
        ...currentConfig.customization,
        name: updates.name ?? currentConfig.customization.name,
        category: updates.category ?? currentConfig.customization.category,
        description: updates.description ?? currentConfig.customization.description,
        tags: updates.tags ?? currentConfig.customization.tags,
      },
    })
  }

  return (
    <ContentContainer>
      <div className="relative">
        <ToolGuideOverlay open={guideOpen} onClose={() => setGuideOpen(false)} />

        <div className="space-y-8">
          <PageHeader
            title="Tool Kataloğu"
            description="SvontAI iş akışınıza ekleyebileceğiniz tool’ları yönetin."
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

        <ToolDetailModal
          tool={selectedTool}
          open={modalOpen}
          onOpenChange={handleModalChange}
          onAddToWorkflow={handleAddToWorkflow}
          onSave={handleSaveTool}
        />
      </div>
    </ContentContainer>
  )
}
