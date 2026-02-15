'use client'

import type { DragEvent } from 'react'
import { GripVertical } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { Tool } from './types'
import { ToolIcon3D } from './ToolIcon3D'

interface ToolCardProps {
  tool: Tool
  onClick: (tool: Tool) => void
  onDragStart: (tool: Tool, event: DragEvent<HTMLDivElement>) => void
}

export function ToolCard({ tool, onClick, onDragStart }: ToolCardProps) {
  return (
    <div
      className={cn(
        'group relative rounded-2xl border border-border/70 bg-card p-4 shadow-soft transition-all duration-300',
        'hover:-translate-y-1 hover:shadow-glow-primary',
        tool.status === 'added' && 'gradient-border-animated bg-primary/5'
      )}
      role="button"
      tabIndex={0}
      onClick={() => onClick(tool)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onClick(tool)
        }
      }}
      draggable
      onDragStart={(event) => onDragStart(tool, event)}
      aria-label={`${tool.name} aracı`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <ToolIcon3D
            toolId={tool.id}
            size="md"
            active
            className={cn(
              'transition-all duration-300',
              tool.status === 'added' && 'ring-2 ring-primary/25'
            )}
          />
          <div>
            <p className="text-sm font-semibold text-foreground">{tool.name}</p>
            <p className="text-xs text-muted-foreground">{tool.description}</p>
          </div>
        </div>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="rounded-lg border border-border/60 bg-muted/40 p-2 text-muted-foreground transition-all duration-300 group-hover:text-foreground group-hover:border-primary/40 group-hover:bg-primary/10">
                <GripVertical className="h-4 w-4" />
              </div>
            </TooltipTrigger>
            <TooltipContent>Workflow alanına sürükleyin</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Badge variant="secondary" className="text-[11px]">
          {tool.category}
        </Badge>
        {tool.tags?.map((tag) => (
          <Badge key={tag} variant="outline" className="text-[11px] transition-colors group-hover:border-primary/40">
            {tag}
          </Badge>
        ))}
        {tool.status === 'added' && (
          <Badge variant="default" className="text-[11px] bg-gradient-to-r from-blue-500 to-violet-600 animate-pulse-glow">
            Workflow'da
          </Badge>
        )}
      </div>
    </div>
  )
}
