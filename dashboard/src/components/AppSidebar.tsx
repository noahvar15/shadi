'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { Stethoscope, ClipboardList, LogOut, FileText, Bell } from 'lucide-react'
import { api } from '@/lib/api'

const NAV_LINK =
  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-900/20 dark:hover:text-emerald-300 transition-colors'

const CHANGE_ROLE_BTN =
  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[var(--foreground-muted)] hover:bg-slate-100 hover:text-[var(--foreground)] dark:hover:bg-slate-700/30 dark:hover:text-[var(--foreground)] transition-colors w-full text-left'

interface ShadiSession {
  role: string
  name: string
}

interface PatientEntry {
  case_id: string
  patient_id: string
  patient_name?: string
  status: string
}

const STATUS_DOT: Record<string, string> = {
  complete: 'bg-emerald-400',
  running: 'bg-amber-400 animate-pulse',
  queued: 'bg-slate-400',
  failed: 'bg-red-400',
}

function PatientList() {
  const [patients, setPatients] = useState<PatientEntry[]>([])

  useEffect(() => {
    let cancelled = false
    api
      .get<PatientEntry[]>('/api/cases')
      .then(({ data }) => {
        if (!cancelled) setPatients(data.slice(0, 10))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (patients.length === 0) {
    return (
      <p className="px-3 py-2 text-xs text-[var(--foreground-muted)] italic">
        — no patients —
      </p>
    )
  }

  return (
    <div className="space-y-0.5">
      {patients.map((p) => (
        <Link
          key={p.case_id}
          href={`/cases/${p.case_id}/triage`}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-[var(--foreground-muted)] hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-900/20 dark:hover:text-emerald-300 transition-colors group"
        >
          <FileText size={13} strokeWidth={1.75} className="shrink-0" />
          <span className="flex-1 truncate">
            {p.patient_name ?? p.patient_id}
          </span>
          <span
            className={`h-1.5 w-1.5 rounded-full shrink-0 ${STATUS_DOT[p.status] ?? 'bg-slate-400'}`}
            title={p.status}
          />
        </Link>
      ))}
    </div>
  )
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
          <Link href="/doctor/notifications" className={NAV_LINK}>
            <Bell size={16} strokeWidth={1.75} />
            Activity
          </Link>

          {/* Per-patient triage notes */}
          <div className="pt-3">
            <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--foreground-muted)]">
              Patients
            </p>
            <PatientList />
          </div>
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
