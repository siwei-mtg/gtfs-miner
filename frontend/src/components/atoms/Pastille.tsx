/**
 * Pastille — chip carré-arrondi qui porte un code ou une lettre de groupe.
 *
 * Inspiré de la signalétique transit (pastille RATP, bullet NYC Subway).
 * Utilisé pour : groupes A–F de la sidebar, route_types, statuts courts,
 * indicateurs d'état compacts.
 *
 * Zéro dépendance maison (règle A0).
 */
import * as React from "react"

import { cn } from "@/lib/utils"

type PastilleTone =
  | "default"
  | "signal"
  | "info"
  | "muted"
  | "destructive"
  | "tram"
  | "metro"
  | "rail"
  | "bus"
  | "ferry"
  | "cable"
  | "funicular"

type PastilleSize = "sm" | "md" | "lg"

const toneClass: Record<PastilleTone, string> = {
  default: "bg-ink text-paper",
  signal: "bg-signal text-signal-foreground",
  info: "bg-info text-paper",
  muted: "bg-secondary text-ink-muted",
  destructive: "bg-destructive text-destructive-foreground",
  tram: "bg-rt-tram text-paper",
  metro: "bg-rt-metro text-paper",
  rail: "bg-rt-rail text-paper",
  bus: "bg-rt-bus text-paper",
  ferry: "bg-rt-ferry text-paper",
  cable: "bg-rt-cable text-paper",
  funicular: "bg-rt-funicular text-paper",
}

const sizeClass: Record<PastilleSize, string> = {
  sm: "h-5 min-w-5 px-1 text-[10px]",
  md: "h-6 min-w-6 px-1.5 text-xs",
  lg: "h-8 min-w-8 px-2 text-sm",
}

interface PastilleProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: PastilleTone
  size?: PastilleSize
}

export const Pastille = React.forwardRef<HTMLSpanElement, PastilleProps>(
  ({ tone = "default", size = "md", className, children, ...rest }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-sm font-mono font-semibold tabular-nums leading-none",
          toneClass[tone],
          sizeClass[size],
          className,
        )}
        {...rest}
      >
        {children}
      </span>
    )
  },
)
Pastille.displayName = "Pastille"
