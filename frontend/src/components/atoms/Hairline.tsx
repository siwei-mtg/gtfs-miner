/**
 * Hairline — diviseur fin (0.5px approximatif via opacity) cartographique.
 *
 * Utilisation : séparer deux sections sans poser une vraie cloison.
 * `orientation="vertical"` rend une ligne verticale (h-full w-px).
 *
 * Zéro dépendance maison (règle A0).
 */
import * as React from "react"

import { cn } from "@/lib/utils"

interface HairlineProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: "horizontal" | "vertical"
  /** Variante pointillée, évoque une isohypse ou une légende de carte. */
  dashed?: boolean
}

export const Hairline = React.forwardRef<HTMLDivElement, HairlineProps>(
  ({ orientation = "horizontal", dashed, className, ...rest }, ref) => {
    return (
      <div
        ref={ref}
        role="separator"
        aria-orientation={orientation}
        className={cn(
          "bg-hair",
          orientation === "horizontal"
            ? "h-px w-full"
            : "h-full w-px",
          dashed &&
            "bg-transparent bg-[image:repeating-linear-gradient(90deg,var(--hair)_0_4px,transparent_4px_8px)]",
          dashed && orientation === "vertical" &&
            "bg-[image:repeating-linear-gradient(180deg,var(--hair)_0_4px,transparent_4px_8px)]",
          className,
        )}
        {...rest}
      />
    )
  },
)
Hairline.displayName = "Hairline"
