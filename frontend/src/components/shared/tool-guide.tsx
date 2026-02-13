'use client'

import { ReactNode, useEffect, useMemo, useState } from 'react'
import { MousePointer2, RotateCcw, X, Minimize2, Maximize2, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface GuideStep {
  id: string
  title: string
  tooltip: string
  pointer: { x: number; y: number }
  highlight: { x: number; y: number; w: number; h: number }
}

interface ToolGuideAssistantProps {
  contextLabel?: string
  initialOpen?: boolean
  loopIntervalMs?: number
  steps?: GuideStep[]
  storageKey?: string
}

const defaultSteps: GuideStep[] = [
  {
    id: 'select',
    title: 'Tool seçimi',
    tooltip: 'Bu tool’u sürükleyerek workflow’unuza ekleyin.',
    pointer: { x: 18, y: 22 },
    highlight: { x: 10, y: 18, w: 30, h: 12 },
  },
  {
    id: 'drag',
    title: 'Sürükle & bırak',
    tooltip: 'Tool’u akış alanına taşıyın, otomatik hizalanır.',
    pointer: { x: 42, y: 36 },
    highlight: { x: 36, y: 30, w: 30, h: 18 },
  },
  {
    id: 'open',
    title: 'Tool sayfası',
    tooltip: 'Entegrasyon adımları panel içinde açılır.',
    pointer: { x: 62, y: 24 },
    highlight: { x: 56, y: 18, w: 30, h: 12 },
  },
  {
    id: 'integrate',
    title: 'Adım adım entegrasyon',
    tooltip: 'Alanları doldurun ve “Devam Et” ile ilerleyin.',
    pointer: { x: 58, y: 50 },
    highlight: { x: 52, y: 44, w: 36, h: 22 },
  },
  {
    id: 'loop',
    title: 'Döngüsel rehber',
    tooltip: 'İsterseniz baştan izleyin veya rehberi gizleyin.',
    pointer: { x: 80, y: 70 },
    highlight: { x: 72, y: 64, w: 20, h: 10 },
  },
]

export function ToolGuideAssistant({
  contextLabel = 'Tool Rehberi',
  initialOpen = false,
  loopIntervalMs = 3600,
  steps = defaultSteps,
  storageKey = 'svontai_tool_guide',
}: ToolGuideAssistantProps) {
  const [open, setOpen] = useState(initialOpen)
  const [minimized, setMinimized] = useState(false)
  const [index, setIndex] = useState(0)

  const activeStep = steps[index]

  useEffect(() => {
    if (!open || minimized) return

    const timer = window.setInterval(() => {
      setIndex((prev) => (prev + 1) % steps.length)
    }, loopIntervalMs)

    return () => window.clearInterval(timer)
  }, [open, minimized, loopIntervalMs, steps.length])

  useEffect(() => {
    const stored = window.localStorage.getItem(storageKey)
    if (!stored) {
      setOpen(initialOpen)
      return
    }
    if (stored === 'dismissed') {
      setOpen(false)
      setMinimized(false)
      return
    }
    if (stored === 'minimized') {
      setOpen(false)
      setMinimized(true)
      return
    }
    if (stored === 'open') {
      setOpen(true)
      setMinimized(false)
    }
  }, [storageKey, initialOpen])

  useEffect(() => {
    const state = minimized ? 'minimized' : open ? 'open' : 'dismissed'
    window.localStorage.setItem(storageKey, state)
  }, [open, minimized, storageKey])

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

  if (!open && !minimized) {
    return (
      <div className="absolute bottom-6 right-6 z-30">
        <Button size="sm" onClick={() => { setOpen(true); setMinimized(false) }}>
          <MousePointer2 className="h-4 w-4 mr-2" />
          Rehberi Başlat
        </Button>
      </div>
    )
  }

  if (minimized) {
    return (
      <div className="absolute bottom-6 right-6 z-30">
        <Button size="sm" variant="outline" onClick={() => { setMinimized(false); setOpen(true) }}>
          <Maximize2 className="h-4 w-4 mr-2" />
          Rehberi Aç
        </Button>
      </div>
    )
  }

  return (
    <div className="absolute inset-0 z-20">
      <div className="absolute inset-0 rounded-3xl border border-border/60 bg-background/40 backdrop-blur-sm" />
      <div className="absolute inset-0 pointer-events-none">
        <div className="guide-highlight guide-pulse" style={highlightStyle} />
        <div className="guide-pointer" style={pointerStyle}>
          <MousePointer2 className="h-5 w-5 text-primary" />
        </div>
        <div
          className="absolute max-w-xs rounded-2xl border border-border/70 bg-card/95 p-4 shadow-elevated"
          style={{ left: `calc(${activeStep.pointer.x}% + 24px)`, top: `calc(${activeStep.pointer.y}% - 12px)` }}
        >
          <Badge variant="outline" className="mb-2">{contextLabel}</Badge>
          <p className="text-sm font-semibold">{activeStep.title}</p>
          <p className="mt-1 text-xs text-muted-foreground">{activeStep.tooltip}</p>
        </div>
      </div>

      <div className="absolute right-6 top-6 flex items-center gap-2">
        <Badge variant="secondary" className="hidden sm:inline-flex">Adım {index + 1}/{steps.length}</Badge>
        <Button size="icon" variant="outline" onClick={() => setIndex((prev) => (prev + 1) % steps.length)}>
          <ArrowRight className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="outline" onClick={() => setIndex(0)}>
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="outline" onClick={() => { setOpen(false); setMinimized(true) }}>
          <Minimize2 className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="destructive" onClick={() => { setOpen(false); setMinimized(false) }}>
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

export function ToolGuideContainer({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('relative', className)}>
      {children}
      <ToolGuideAssistant />
    </div>
  )
}
