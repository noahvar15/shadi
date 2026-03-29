'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Stethoscope, ClipboardList, ArrowLeft } from 'lucide-react'

const NAV_LINK =
  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-900/20 dark:hover:text-violet-300 transition-colors'

const CHANGE_ROLE_BTN =
  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-slate-100 hover:text-[var(--foreground)] dark:hover:bg-slate-700/30 dark:hover:text-[var(--foreground)] transition-colors w-full text-left'

interface ShadiSession {
  role: string
  name: string
}

export function AppSidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [session, setSession] = useState<ShadiSession | null>(null)

  useEffect(() => {
    try {
      const raw = localStorage.getItem('shadi_session')
      if (raw) setSession(JSON.parse(raw))
    } catch {
      // ignore
    }
  }, [])

  function handleChangeRole() {
    localStorage.removeItem('shadi_session')
    router.push('/')
  }

  if (pathname === '/') return null

  const isNurse = pathname.startsWith('/nurse')
  const isDoctor = pathname.startsWith('/doctor') || pathname.startsWith('/cases')

  if (isNurse) {
    return (
      <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
        <div className="h-16 flex items-center px-5 border-b border-[var(--border)]">
          <Stethoscope size={18} className="text-violet-600 dark:text-violet-400 mr-2" strokeWidth={1.75} />
          <div className="flex flex-col min-w-0">
            <span className="text-lg font-bold text-violet-600 dark:text-violet-400 leading-tight">Shadi</span>
            {session?.name && (
              <span className="text-xs text-[var(--foreground-muted)] truncate leading-tight">
                {session.name}
              </span>
            )}
          </div>
          <span className="ml-2 text-[10px] font-medium text-[var(--foreground-muted)] tracking-wide uppercase leading-tight hidden lg:block shrink-0">
            Nurse
          </span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          <Link href="/nurse" className={NAV_LINK}>
            <Stethoscope size={16} strokeWidth={1.75} />
            Triage Intake
          </Link>
        </nav>

        <div className="px-3 pb-4 space-y-0.5 border-t border-[var(--border)] pt-3">
          <button onClick={handleChangeRole} className={CHANGE_ROLE_BTN}>
            <ArrowLeft size={16} strokeWidth={1.75} />
            Change Role
          </button>
        </div>
      </aside>
    )
  }

  if (isDoctor) {
    return (
      <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
        <div className="h-16 flex items-center px-5 border-b border-[var(--border)]">
          <ClipboardList size={18} className="text-violet-600 dark:text-violet-400 mr-2" strokeWidth={1.75} />
          <div className="flex flex-col min-w-0">
            <span className="text-lg font-bold text-violet-600 dark:text-violet-400 leading-tight">Shadi</span>
            {session?.name && (
              <span className="text-xs text-[var(--foreground-muted)] truncate leading-tight">
                {session.name}
              </span>
            )}
          </div>
          <span className="ml-2 text-[10px] font-medium text-[var(--foreground-muted)] tracking-wide uppercase leading-tight hidden lg:block shrink-0">
            Doctor
          </span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          <Link href="/doctor" className={NAV_LINK}>
            <ClipboardList size={16} strokeWidth={1.75} />
            Active Cases
          </Link>
        </nav>

        <div className="px-3 pb-4 space-y-0.5 border-t border-[var(--border)] pt-3">
          <button onClick={handleChangeRole} className={CHANGE_ROLE_BTN}>
            <ArrowLeft size={16} strokeWidth={1.75} />
            Change Role
          </button>
        </div>
      </aside>
    )
  }

  // Fallback for unknown paths
  return (
    <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
      <div className="h-16 flex items-center px-5 border-b border-[var(--border)]">
        <span className="text-lg font-bold text-violet-600 dark:text-violet-400">Shadi</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        <Link href="/" className={NAV_LINK}>
          Home
        </Link>
        <Link href="/nurse" className={NAV_LINK}>
          <Stethoscope size={16} strokeWidth={1.75} />
          Nurse
        </Link>
        <Link href="/doctor" className={NAV_LINK}>
          <ClipboardList size={16} strokeWidth={1.75} />
          Doctor
        </Link>
      </nav>
    </aside>
  )
}
