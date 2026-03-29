'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import {
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
  FileText,
  Bell,
} from 'lucide-react'
import { api } from '@/lib/api'

interface CaseSummary {
  case_id: string
  patient_id: string
  patient_name?: string
  status: string
  created_at: string
  chief_complaint?: string
}

const STATUS_META: Record<
  string,
  { label: string; icon: React.ReactNode; pill: string }
> = {
  complete: {
    label: 'Report ready',
    icon: <CheckCircle2 size={15} className="text-emerald-500" />,
    pill: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  },
  running: {
    label: 'Analysing',
    icon: <Loader2 size={15} className="text-amber-500 animate-spin" />,
    pill: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  },
  queued: {
    label: 'Queued',
    icon: <Clock size={15} className="text-slate-400" />,
    pill: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
  },
  failed: {
    label: 'Failed',
    icon: <XCircle size={15} className="text-red-500" />,
    pill: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  },
}

function getMeta(status: string) {
  return (
    STATUS_META[status] ?? {
      label: status,
      icon: <Clock size={15} className="text-slate-400" />,
      pill: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
    }
  )
}

function NotificationRow({ c }: { c: CaseSummary }) {
  const meta = getMeta(c.status)
  return (
    <div className="flex items-start gap-4 p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl hover:border-emerald-400 dark:hover:border-emerald-600 transition-colors">
      <div className="mt-0.5 shrink-0">{meta.icon}</div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-[var(--foreground)]">
            {c.patient_name ?? c.patient_id}
          </span>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${meta.pill}`}
          >
            {meta.label}
          </span>
        </div>
        <p className="text-xs text-[var(--foreground-muted)] mt-0.5 font-mono">
          {c.case_id}
        </p>
        {c.chief_complaint && (
          <p className="text-xs text-[var(--foreground-muted)] mt-1 line-clamp-1">
            {c.chief_complaint.split('\n')[0]}
          </p>
        )}
        <p className="text-xs text-[var(--foreground-muted)] mt-1">
          {new Date(c.created_at).toLocaleString(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short',
          })}
        </p>
      </div>
      <div className="flex flex-col gap-1.5 shrink-0">
        {c.status === 'complete' && (
          <Link
            href={`/cases/${c.case_id}`}
            className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400 hover:underline font-medium"
          >
            <CheckCircle2 size={12} /> View report
          </Link>
        )}
        <Link
          href={`/cases/${c.case_id}/triage`}
          className="flex items-center gap-1 text-xs text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
        >
          <FileText size={12} /> Triage note
        </Link>
      </div>
    </div>
  )
}

export default function NotificationsPage() {
  const { data, isLoading, error } = useQuery<CaseSummary[]>({
    queryKey: ['cases'],
    queryFn: () => api.get<CaseSummary[]>('/api/cases').then((r) => r.data),
    refetchInterval: 10_000,
  })

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Bell className="text-[var(--foreground-muted)]" size={20} strokeWidth={1.75} />
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Activity</h1>
          <p className="text-sm text-[var(--foreground-muted)] mt-0.5">
            All cases — live pipeline status
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="animate-pulse h-24 rounded-xl bg-slate-200 dark:bg-slate-800"
            />
          ))}
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">
          Failed to load activity. The API may be unavailable.
        </div>
      )}

      {!isLoading && !error && data?.length === 0 && (
        <div className="text-center py-20 text-[var(--foreground-muted)]">
          <Bell size={40} strokeWidth={1.25} className="mx-auto mb-3 opacity-40" />
          <p className="text-sm">No cases submitted yet.</p>
        </div>
      )}

      {!isLoading && !error && data && data.length > 0 && (
        <div className="space-y-2">
          {data.map((c) => (
            <NotificationRow key={c.case_id} c={c} />
          ))}
        </div>
      )}
    </div>
  )
}
