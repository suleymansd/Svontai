'use client'

import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, MousePointer2, RotateCcw, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface GuideStep {
  id: string
  title: string
  tooltip: string
  pointer: { x: number; y: number }
  highlight: { x: number; y: number; w: number; h: number }
}

interface ToolGuideOverlayProps {
  open: boolean
  onClose: () => void
  steps?: GuideStep[]
  loopIntervalMs?: number
  className?: string
}

const defaultSteps: GuideStep[] = [
  {
    id: 'select',
    title: 'Tool seçimi',
    tooltip: 'Bu tool’u sürükleyerek workflow’unuza ekleyin.',
    pointer: { x: 12, y: 24 },
    highlight: { x: 8, y: 20, w: 32, h: 18 },
  },
  {
    id: 'drag',
    title: 'Sürükle & bırak',
    tooltip: 'Tool’u akış alanına bırakın, otomatik hizalanır.',
    pointer: { x: 42, y: 36 },
    highlight: { x: 36, y: 28, w: 32, h: 20 },
  },
  {
    id: 'drop',
    title: 'Workflow alanı',
    tooltip: 'Tool eklendiğinde başarı animasyonu görünür.',
    pointer: { x: 68, y: 56 },
    highlight: { x: 52, y: 44, w: 40, h: 26 },
  },
  {
    id: 'settings',
    title: 'Ayar ekranı',
    tooltip: 'Ayar ekranını açıp adım adım ilerleyin.',
    pointer: { x: 70, y: 24 },
    highlight: { x: 62, y: 18, w: 28, h: 14 },
  },
  {
    id: 'next',
    title: 'Devam et',
    tooltip: 'Devam Et ile sonraki adımı görün.',
    pointer: { x: 84, y: 84 },
    highlight: { x: 76, y: 78, w: 18, h: 10 },
  },
]

export function ToolGuideOverlay({
  open,
  onClose,
  steps = defaultSteps,
  loopIntervalMs = 2800,
  className,
}: ToolGuideOverlayProps) {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (!open) return
    const timer = window.setInterval(() => {
      setIndex((prev) => (prev + 1) % steps.length)
    }, loopIntervalMs)
    return () => window.clearInterval(timer)
  }, [open, loopIntervalMs, steps.length])

  useEffect(() => {
    if (!open) {
      setIndex(0)
    }
  }, [open])

  const activeStep = steps[index]

  const highlightStyle = useMemo(() => ({
    left: `${activeStep.highlight.x}%`,
    top: `${activeStep.highlight.y}%`,
    width: `${activeStep.highlight.w}%`,
    height: `${activeStep.highlight.h}%`,
  }), [activeStep])

  const pointerStyle = useMemo(() => ({
    left: `${activeStep.pointer.x}%`,
    top: `${activeStep.pointer.y}%`,
  }), [activeStep])

  if (!open) return null

  return (
    <div className={cn('absolute inset-0 z-30', className)} aria-hidden={!open}>
      <div className="absolute inset-0 rounded-3xl border border-border/60 bg-background/40 backdrop-blur-sm" />
      <div className="absolute inset-0 pointer-events-none">
        <div className="guide-highlight guide-pulse" style={highlightStyle} />
        <div className="guide-pointer" style={pointerStyle}>
          <MousePointer2 className="h-5 w-5 text-primary" />
        </div>
        <div
          className="absolute max-w-xs rounded-2xl border border-border/70 bg-card/95 p-4 shadow-elevated"
          style={{ left: `calc(${activeStep.pointer.x}% + 22px)`, top: `calc(${activeStep.pointer.y}% - 12px)` }}
        >
          <Badge variant="outline" className="mb-2">
            Rehber
          </Badge>
          <p className="text-sm font-semibold">{activeStep.title}</p>
          <p className="mt-1 text-xs text-muted-foreground">{activeStep.tooltip}</p>
        </div>
      </div>

      <div className="absolute bottom-6 right-6 flex items-center gap-2">
        <Badge variant="secondary" className="hidden sm:inline-flex">
          Adım {index + 1}/{steps.length}
        </Badge>
        <Button size="sm" variant="outline" onClick={() => setIndex((prev) => (prev + 1) % steps.length)}>
          Devam Et
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
        <Button size="icon" variant="outline" onClick={() => setIndex(0)} aria-label="Baştan izle">
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="destructive" onClick={onClose} aria-label="Rehberi kapat">
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
