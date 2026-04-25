/**
 * CodeTag — petite puce mono pour tout identifiant affiché in-line
 * (ID projet, code table, référence technique).
 *
 * Reste simple : rien à personnaliser sauf `className`.
 * Zéro dépendance maison (règle A0).
 */
import * as React from "react"

import { cn } from "@/lib/utils"

export const CodeTag = React.forwardRef<
  HTMLElement,
  React.HTMLAttributes<HTMLElement>
>(({ className, children, ...rest }, ref) => {
  return (
    <code
      ref={ref}
      className={cn(
        "inline-flex items-center rounded-sm bg-secondary px-1.5 py-0.5 font-mono text-[11px] font-medium leading-tight text-ink",
        className,
      )}
      {...rest}
    >
      {children}
    </code>
  )
})
CodeTag.displayName = "CodeTag"
