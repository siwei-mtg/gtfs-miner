import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { AppHeader } from '@/components/organisms/AppHeader'
import type { UserResponse } from '@/types/api'

interface AppShellProps {
  user: UserResponse | null
  onLogout: () => void
  children: ReactNode
  className?: string
}

export function AppShell({ user, onLogout, children, className }: AppShellProps) {
  return (
    <div className={cn('min-h-svh flex flex-col', className)}>
      {user && <AppHeader email={user.email} onLogout={onLogout} />}
      <main className="flex-1 max-w-[1280px] mx-auto w-full px-6 py-8">
        {children}
      </main>
    </div>
  )
}
