/**
 * usePlan — thin accessor for the current user's tenant plan (Task 40B).
 *
 * Treats an absent or unknown user as 'free' so gated UI renders its
 * fallback instead of crashing while auth is still loading.
 */
import { useAuthContext } from '@/contexts/AuthContext'
import type { Plan } from '@/types/api'

export const PLAN_ORDER: Record<Plan, number> = {
  free: 0,
  pro: 1,
  enterprise: 2,
}

export function usePlan() {
  const { user } = useAuthContext()
  const plan: Plan = (user?.plan as Plan | undefined) ?? 'free'
  return {
    plan,
    isFree: plan === 'free',
    isPro: plan === 'pro',
    isEnterprise: plan === 'enterprise',
    /** True if the current plan meets or exceeds the required tier. */
    hasAtLeast: (required: Plan) => PLAN_ORDER[plan] >= PLAN_ORDER[required],
  }
}
