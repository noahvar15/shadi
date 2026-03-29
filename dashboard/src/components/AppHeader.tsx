'use client'

import { usePathname } from 'next/navigation'
import { DarkModeToggle } from '@/components/DarkModeToggle'

export function AppHeader() {
  const pathname = usePathname()

  if (pathname === '/') return null

  return (
    <header className="h-16 flex-shrink-0 flex items-center gap-4 px-6 bg-[var(--surface)] border-b border-[var(--border)]">
      <div className="flex-1 max-w-sm">
        <input
          type="search"
          placeholder="Search patients..."
          aria-label="Search patients"
          disabled
          className="w-full px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] opacity-60 cursor-not-allowed focus:outline-none"
        />
      </div>

      <div className="flex items-center gap-2 ml-auto">
        <DarkModeToggle />
        <div
          className="h-8 w-8 rounded-full bg-violet-600 flex items-center justify-center text-white text-xs font-semibold select-none"
          title="User account"
        >
          ES
        </div>
      </div>
    </header>
  )
}
