import { cn } from '@/lib/utils'
import { Button } from '@/components/atoms/button'

interface AppHeaderProps {
  email: string
  onLogout: () => void
  className?: string
}

export function AppHeader({ email, onLogout, className }: AppHeaderProps) {
  return (
    <header className={cn(
      'flex items-center justify-between px-6 h-14 border-b border-border bg-background',
      className
    )}>
      <span className="font-semibold text-lg text-foreground">GTFS Miner</span>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{email}</span>
        <Button variant="ghost" size="sm" onClick={onLogout}>Logout</Button>
      </div>
    </header>
  )
}
