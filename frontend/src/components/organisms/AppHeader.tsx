import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/atoms/button'
import { Moon, Sun } from 'lucide-react'

interface AppHeaderProps {
  email: string
  onLogout: () => void
  className?: string
}

/** Bascule light/dark — persisté dans localStorage, respecte prefers-color-scheme au premier rendu. */
function useThemeToggle() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    if (typeof document === 'undefined') return false
    return document.documentElement.classList.contains('dark')
  })

  useEffect(() => {
    const root = document.documentElement
    if (isDark) root.classList.add('dark')
    else root.classList.remove('dark')
    try {
      localStorage.setItem('gtfs-miner:theme', isDark ? 'dark' : 'light')
    } catch {
      // Environnements sans localStorage (jsdom, etc.) — ignoré volontairement.
    }
  }, [isDark])

  return { isDark, toggle: () => setIsDark((v) => !v) }
}

export function AppHeader({ email, onLogout, className }: AppHeaderProps) {
  const { isDark, toggle } = useThemeToggle()

  return (
    <header
      className={cn(
        'flex items-center justify-between px-6 h-14 border-b border-hair bg-card',
        className,
      )}
    >
      <span className="font-display text-xl font-medium leading-none text-ink">
        GTFS Miner
      </span>
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs text-ink-muted">{email}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={toggle}
          aria-label={isDark ? 'Passer en mode clair' : 'Passer en mode sombre'}
          className="h-8 w-8 p-0 text-ink-muted hover:text-ink"
        >
          {isDark ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={onLogout}
          className="h-8 gap-1.5 px-2 text-ink-muted hover:text-ink"
        >
          Logout
        </Button>
      </div>
    </header>
  )
}
