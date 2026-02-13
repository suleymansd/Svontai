'use client'

import type { DragEvent } from 'react'
import { useState } from 'react'
import { CheckCircle2, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { Tool } from './types'

interface ToolDropZoneProps {
  tools: Tool[]
  onDropTool: (toolId: string) => void
}

export function ToolDropZone({ tools, onDropTool }: ToolDropZoneProps) {
  const [isOver, setIsOver] = useState(false)
  const [lastDropped, setLastDropped] = useState<string | null>(null)

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsOver(true)
  }

  const handleDragLeave = () => setIsOver(false)

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsOver(false)
    const toolId = event.dataTransfer.getData('text/plain')
    if (toolId) {
      onDropTool(toolId)
      setLastDropped(toolId)
      window.setTimeout(() => setLastDropped(null), 1200)
    }
  }

  return (
    <div
      className={cn(
        'relative rounded-3xl border border-dashed border-border/70 bg-muted/30 p-6 transition-all',
        isOver && 'border-primary/60 bg-primary/5 shadow-soft',
        lastDropped && 'border-emerald-500/60 bg-emerald-500/5'
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      aria-label="Workflow alanı"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">Workflow Alanı</p>
          <p className="text-xs text-muted-foreground">Tool’ları buraya sürükleyin</p>
        </div>
        <Badge variant="outline" className="gap-1">
          <Sparkles className="h-3 w-3" />
          {tools.length} aktif
        </Badge>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {tools.length === 0 ? (
          <div className="rounded-2xl border border-border/60 bg-card p-4 text-sm text-muted-foreground">
            Henüz workflow’a eklenen tool yok.
          </div>
        ) : (
          tools.map((tool) => (
            <div
              key={tool.id}
              className={cn(
                'rounded-2xl border border-border/60 bg-card px-4 py-3 text-sm font-medium transition-all',
                lastDropped === tool.id && 'border-emerald-500/70 bg-emerald-500/10'
              )}
            >
              <div className="flex items-center justify-between">
                <span>{tool.name}</span>
                {lastDropped === tool.id && (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                )}
              </div>
              <p className="text-xs text-muted-foreground">{tool.category}</p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
