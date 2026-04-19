/**
 * PlanGate — conditionally renders children based on the current user's
 *             tenant plan (Task 40B).
 *
 * Lives in `molecules/` (not `atoms/`) because it transitively depends on
 * AuthContext — A0 (atoms zero-deps rule) forbids that kind of coupling
 * at the atom layer.
 */
import type { ReactNode } from 'react'
import type { Plan } from '@/types/api'
import { usePlan } from '@/hooks/usePlan'

interface Props {
  /** Minimum plan required to reveal the children. */
  plan: Plan
  /** Rendered when the current plan is below `plan` (default: nothing). */
  fallback?: ReactNode
  children: ReactNode
}

export function PlanGate({ plan, fallback = null, children }: Props) {
  const { hasAtLeast } = usePlan()
  return <>{hasAtLeast(plan) ? children : fallback}</>
}
