'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Stethoscope, ClipboardList, LogOut } from 'lucide-react'

const NAV_LINK =
  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-900/20 dark:hover:text-emerald-300 transition-colors'

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
      else setSession(null)
    } catch {
      // ignore
    }
  }, [pathname])

  function handleChangeRole() {
    localStorage.removeItem('shadi_session')
    setSession(null)
    router.push('/')
  }

  if (pathname === '/') return null

  // Role from session is authoritative; fall back to pathname inference while session loads.
  const role = session?.role ?? (pathname.startsWith('/nurse') ? 'nurse' : 'doctor')
  const isNurse = role === 'nurse'
  const isDoctor = role === 'doctor'

  if (isNurse) {
    return (
      <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
        <div className="flex flex-col px-5 py-3 border-b border-[var(--border)] gap-0.5">
          <div className="flex items-center gap-2">
            <Stethoscope size={17} className="text-emerald-600 dark:text-emerald-400 shrink-0" strokeWidth={1.75} />
            <span className="text-base font-bold text-emerald-600 dark:text-emerald-400 leading-tight">Shadi</span>
            <span className="ml-auto text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 tracking-widest uppercase bg-emerald-50 dark:bg-emerald-900/30 px-1.5 py-0.5 rounded shrink-0">
              Nurse
            </span>
          </div>
          {session?.name && (
            <span className="text-xs text-[var(--foreground-muted)] truncate pl-[25px]">
              {session.name}
            </span>
          )}
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          <Link href="/nurse" className={NAV_LINK}>
            <Stethoscope size={16} strokeWidth={1.75} />
            Triage Intake
          </Link>
        </nav>

        <div className="px-3 pb-4 space-y-0.5 border-t border-[var(--border)] pt-3">
          <button onClick={handleChangeRole} className={CHANGE_ROLE_BTN}>
            <LogOut size={16} strokeWidth={1.75} />
            Sign Out
          </button>
        </div>
      </aside>
    )
  }

  if (isDoctor) {
    return (
      <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
        <div className="flex flex-col px-5 py-3 border-b border-[var(--border)] gap-0.5">
          <div className="flex items-center gap-2">
            <ClipboardList size={17} className="text-emerald-600 dark:text-emerald-400 shrink-0" strokeWidth={1.75} />
            <span className="text-base font-bold text-emerald-600 dark:text-emerald-400 leading-tight">Shadi</span>
            <span className="ml-auto text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 tracking-widest uppercase bg-emerald-50 dark:bg-emerald-900/30 px-1.5 py-0.5 rounded shrink-0">
              Doctor
            </span>
          </div>
          {session?.name && (
            <span className="text-xs text-[var(--foreground-muted)] truncate pl-[25px]">
              {session.name}
            </span>
          )}
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          <Link href="/doctor" className={NAV_LINK}>
            <ClipboardList size={16} strokeWidth={1.75} />
            Active Cases
          </Link>
          <Link href="/nurse" className={NAV_LINK}>
            <Stethoscope size={16} strokeWidth={1.75} />
            Triage Intake
          </Link>
        </nav>

        <div className="px-3 pb-4 space-y-0.5 border-t border-[var(--border)] pt-3">
          <button onClick={handleChangeRole} className={CHANGE_ROLE_BTN}>
            <LogOut size={16} strokeWidth={1.75} />
            Sign Out
          </button>
        </div>
      </aside>
    )
  }

  // Fallback for unknown paths
  return (
    <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
      <div className="h-16 flex items-center px-5 border-b border-[var(--border)]">
        <span className="text-lg font-bold text-emerald-600 dark:text-emerald-400">Shadi</span>
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
