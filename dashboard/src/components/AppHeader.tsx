'use client'

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { DarkModeToggle } from '@/components/DarkModeToggle'

function getInitials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function AppHeader() {
  const pathname = usePathname()
  const [initials, setInitials] = useState('')

  // Re-read on every route change so the avatar updates immediately after login/logout.
  useEffect(() => {
    try {
      const raw = localStorage.getItem('shadi_session')
      if (raw) {
        const { name } = JSON.parse(raw)
        setInitials(name ? getInitials(name) : '')
      } else {
        setInitials('')
      }
    } catch {
      setInitials('')
    }
  }, [pathname])

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
        {initials && (
          <div
            className="h-8 w-8 rounded-full bg-emerald-600 flex items-center justify-center text-white text-xs font-semibold select-none"
            title="Signed in user"
          >
            {initials}
          </div>
        )}
      </div>
    </header>
  )
}
