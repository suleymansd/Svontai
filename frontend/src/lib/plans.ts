export const PLAN_ORDER = ['free', 'pro', 'premium', 'enterprise'] as const

export type PlanCode = (typeof PLAN_ORDER)[number]

const PLAN_LEVELS: Record<PlanCode, number> = {
  free: 0,
  pro: 1,
  premium: 2,
  enterprise: 3,
}

const LEGACY_PLAN_ALIASES: Record<string, PlanCode> = {
  starter: 'pro',
  growth: 'premium',
  business: 'enterprise',
}

export const PLAN_LABELS: Record<PlanCode, string> = {
  free: 'Ücretsiz',
  pro: 'Pro',
  premium: 'Premium',
  enterprise: 'Kurumsal',
}

export function normalizePlanCode(value: string | null | undefined): PlanCode {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return 'free'
  const aliased = LEGACY_PLAN_ALIASES[normalized] || normalized
  if (PLAN_ORDER.includes(aliased as PlanCode)) {
    return aliased as PlanCode
  }
  return 'free'
}

export function planMeetsRequirement(currentPlan: string | null | undefined, requiredPlan: string | null | undefined): boolean {
  const current = normalizePlanCode(currentPlan)
  const required = normalizePlanCode(requiredPlan)
  return PLAN_LEVELS[current] >= PLAN_LEVELS[required]
}
