'use client'

import { useEffect, useRef, useState } from 'react'
import { usePathname } from 'next/navigation'
import { Bell, CheckCircle2, Clock, Loader2, XCircle } from 'lucide-react'
import Link from 'next/link'
import { api } from '@/lib/api'

interface CaseSummary {
  case_id: string
  patient_id: string
  patient_name?: string
  status: string
  created_at: string
}

interface Notification {
  case_id: string
  patient_id: string
  patient_name?: string
  status: string
  created_at: string
  seen: boolean
}

const SEEN_KEY = 'shadi_seen_cases'

function getSeenSet(): Set<string> {
  try {
    const raw = localStorage.getItem(SEEN_KEY)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch {
    return new Set()
  }
}

function markAllSeen(caseIds: string[]): void {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(caseIds))
  } catch {
    // ignore
  }
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'complete') {
    return <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />
  }
  if (status === 'processing') {
    return <Loader2 size={14} className="text-amber-500 shrink-0 animate-spin" />
  }
  if (status === 'failed' || status === 'enqueue_failed') {
    return <XCircle size={14} className="text-red-500 shrink-0" />
  }
  return <Clock size={14} className="text-slate-400 shrink-0" />
}

function statusLabel(status: string): string {
  switch (status) {
    case 'complete': return 'Report ready'
    case 'processing': return 'Analysis running'
    case 'queued': return 'Queued'
    case 'pending_enqueue': return 'Pending'
    case 'failed': return 'Pipeline failed'
    case 'enqueue_failed': return 'Queue failed'
    default: return status
  }
}

export function NotificationBell() {
  const pathname = usePathname()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const isDoctor =
    pathname.startsWith('/doctor') || pathname.startsWith('/cases')

  // Fetch cases and derive notifications
  useEffect(() => {
    if (!isDoctor) return
    let cancelled = false

    async function load() {
      try {
        const { data } = await api.get<CaseSummary[]>('/api/cases')
        if (cancelled) return
        const seen = getSeenSet()
        setNotifications(
          data.map((c) => ({
            case_id: c.case_id,
            patient_id: c.patient_id,
            patient_name: c.patient_name,
            status: c.status,
            created_at: c.created_at,
            seen: seen.has(c.case_id),
          }))
        )
      } catch {
        // silently ignore — header must not break page on API error
      }
    }

    load()
    const interval = setInterval(load, 10_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [isDoctor])

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!isDoctor) return null

  const unseen = notifications.filter((n) => !n.seen)
  const unseenCount = unseen.length

  function handleOpen() {
    setOpen((v) => !v)
    if (!open) {
      // Mark all as seen when opening
      markAllSeen(notifications.map((n) => n.case_id))
      setNotifications((prev) => prev.map((n) => ({ ...n, seen: true })))
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={handleOpen}
        aria-label={`Notifications${unseenCount > 0 ? `, ${unseenCount} unread` : ''}`}
        className="relative p-1.5 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
      >
        <Bell size={18} strokeWidth={1.75} />
        {unseenCount > 0 && (
          <span className="absolute top-0.5 right-0.5 h-4 min-w-4 px-0.5 flex items-center justify-center bg-amber-400 text-slate-900 text-[10px] font-bold rounded-full leading-none">
            {unseenCount > 9 ? '9+' : unseenCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
            <span className="text-sm font-semibold text-[var(--foreground)]">
              Notifications
            </span>
            {notifications.length > 0 && (
              <span className="text-xs text-[var(--foreground-muted)]">
                {notifications.length} case{notifications.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border)]">
            {notifications.length === 0 && (
              <p className="px-4 py-6 text-sm text-center text-[var(--foreground-muted)]">
                No notifications yet
              </p>
            )}
            {notifications.slice(0, 8).map((n) => (
              <Link
                key={n.case_id}
                href={`/cases/${n.case_id}`}
                onClick={() => setOpen(false)}
                className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
              >
                <StatusIcon status={n.status} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[var(--foreground)] truncate">
                    {n.patient_name ?? n.patient_id}
                  </p>
                  <p className="text-xs text-[var(--foreground-muted)] mt-0.5">
                    {statusLabel(n.status)} ·{' '}
                    {new Date(n.created_at).toLocaleTimeString(undefined, {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
                {!n.seen && (
                  <span className="mt-1 h-2 w-2 rounded-full bg-amber-400 shrink-0" />
                )}
              </Link>
            ))}
          </div>

          <div className="border-t border-[var(--border)] px-4 py-2.5">
            <Link
              href="/doctor/notifications"
              onClick={() => setOpen(false)}
              className="text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:underline"
            >
              View all activity →
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
