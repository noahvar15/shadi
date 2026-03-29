'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Stethoscope, ClipboardList, ArrowLeft } from 'lucide-react'

const NAV_LINK =
  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-900/20 dark:hover:text-violet-300 transition-colors'

const CHANGE_ROLE_LINK =
  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-slate-100 hover:text-[var(--foreground)] dark:hover:bg-slate-700/30 dark:hover:text-[var(--foreground)] transition-colors'

export function AppSidebar() {
  const pathname = usePathname()

  if (pathname === '/') return null

  const isNurse = pathname.startsWith('/nurse')
  const isDoctor = pathname.startsWith('/doctor') || pathname.startsWith('/cases')

  if (isNurse) {
    return (
      <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
        <div className="h-16 flex items-center px-5 border-b border-[var(--border)]">
          <Stethoscope size={18} className="text-violet-600 dark:text-violet-400 mr-2" strokeWidth={1.75} />
          <span className="text-lg font-bold text-violet-600 dark:text-violet-400">Shadi</span>
          <span className="ml-2 text-[10px] font-medium text-[var(--foreground-muted)] tracking-wide uppercase leading-tight hidden lg:block">
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
          <Link href="/" className={CHANGE_ROLE_LINK}>
            <ArrowLeft size={16} strokeWidth={1.75} />
            Change Role
          </Link>
        </div>
      </aside>
    )
  }

  if (isDoctor) {
    return (
      <aside className="hidden md:flex flex-col w-56 flex-shrink-0 bg-[var(--surface)] border-r border-[var(--border)]">
        <div className="h-16 flex items-center px-5 border-b border-[var(--border)]">
          <ClipboardList size={18} className="text-violet-600 dark:text-violet-400 mr-2" strokeWidth={1.75} />
          <span className="text-lg font-bold text-violet-600 dark:text-violet-400">Shadi</span>
          <span className="ml-2 text-[10px] font-medium text-[var(--foreground-muted)] tracking-wide uppercase leading-tight hidden lg:block">
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
          <Link href="/" className={CHANGE_ROLE_LINK}>
            <ArrowLeft size={16} strokeWidth={1.75} />
            Change Role
          </Link>
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
