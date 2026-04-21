/**
 * EditorialStat — ratio éditorial 3:1 data/label.
 *
 *   ┌────────────────────┐
 *   │ LABEL UPPERCASE    │  ← 10px tracking-[0.15em] muted
 *   │                    │
 *   │  1 247             │  ← Fraunces (display), 28–40px tabular
 *   │                    │
 *   │ · optional hint    │  ← 11px muted-italic (hors ligne)
 *   └────────────────────┘
 *
 * Utilisé dans : KpiRibbon du dashboard, fiches projet, stats latérales.
 * Composé de 2 éléments → molecule (règles Atomic Design).
 */
import * as React from "react"

import { cn } from "@/lib/utils"

type StatSize = "sm" | "md" | "lg"

const valueSize: Record<StatSize, string> = {
  sm: "text-[20px]",
  md: "text-[28px]",
  lg: "text-[40px]",
}

interface EditorialStatProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
  /** Accepté en string (déjà formaté) ou en number (sera localisé fr-FR). */
  value: React.ReactNode
  /** Ligne d'appoint, italique muted — e.g. unité, delta. */
  hint?: React.ReactNode
  /** Icône Lucide optionnelle à gauche du label. */
  icon?: React.ReactNode
  size?: StatSize
  /** `true` → utiliser Fraunces (display serif) au lieu de General Sans. */
  display?: boolean
  /** État de chargement — skeleton discret à la place de la valeur. */
  loading?: boolean
}

export const EditorialStat = React.forwardRef<
  HTMLDivElement,
  EditorialStatProps
>(
  (
    {
      label,
      value,
      hint,
      icon,
      size = "md",
      display = true,
      loading,
      className,
      ...rest
    },
    ref,
  ) => {
    const formatted =
      typeof value === "number" ? new Intl.NumberFormat("fr-FR").format(value) : value

    return (
      <div
        ref={ref}
        className={cn("flex flex-col gap-1", className)}
        {...rest}
      >
        <span className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.15em] text-ink-muted">
          {icon && <span aria-hidden className="opacity-70">{icon}</span>}
          {label}
        </span>
        {loading ? (
          <span
            aria-hidden
            className={cn(
              "h-[1em] w-20 animate-pulse rounded-sm bg-secondary",
              valueSize[size],
            )}
          />
        ) : (
          <span
            className={cn(
              "leading-none tabular-nums text-ink",
              display ? "font-display font-medium" : "font-sans font-semibold",
              valueSize[size],
            )}
          >
            {formatted}
          </span>
        )}
        {hint && (
          <span className="text-[11px] italic text-ink-muted">{hint}</span>
        )}
      </div>
    )
  },
)
EditorialStat.displayName = "EditorialStat"
