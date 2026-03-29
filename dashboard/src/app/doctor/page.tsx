'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Stethoscope } from 'lucide-react'
import { api } from '@/lib/api'

interface Case {
  case_id: string
  patient_id: string
  patient_name?: string
  status: string
  created_at: string
  chief_complaint?: string
}

const STATUS_STYLES: Record<string, string> = {
  complete: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  processing: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  queued: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
  pending_enqueue: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
  enqueue_failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}

function SkeletonCard() {
  return (
    <div className="animate-pulse bg-slate-200 dark:bg-slate-800 rounded h-20" />
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <Stethoscope className="w-12 h-12 text-slate-300 dark:text-slate-600 mb-4" />
      <h2 className="text-lg font-semibold text-slate-700 dark:text-slate-300 mb-1">
        No cases yet
      </h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-xs">
        Submit a new patient case to begin diagnostic reasoning.
      </p>
      <Link
        href="/nurse"
        className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-md transition-colors"
      >
        New Case
      </Link>
    </div>
  )
}

const STATUS_LABELS: Record<string, string> = {
  complete: 'Complete',
  processing: 'Processing',
  queued: 'Queued',
  pending_enqueue: 'Pending',
  enqueue_failed: 'Failed to Queue',
  failed: 'Failed',
}

function CaseCard({ c }: { c: Case }) {
  const displayName = c.patient_name || c.patient_id
  const chiefComplaintLine = c.chief_complaint
    ?.split('\n')
    .find((l) => l.startsWith('Chief Complaint:'))
    ?.replace('Chief Complaint:', '')
    .trim()
  const summary = chiefComplaintLine || c.chief_complaint?.split('\n')[0] || ''

  return (
    <Link
      href={`/cases/${c.case_id}`}
      className="block p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg hover:border-emerald-400 dark:hover:border-emerald-600 transition-colors"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
            {displayName}
          </p>
          {summary && (
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1 line-clamp-2">
              {summary}
            </p>
          )}
          <p className="text-xs font-mono text-slate-400 dark:text-slate-500 mt-1.5">
            {c.case_id}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[c.status] ?? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'}`}
          >
            {STATUS_LABELS[c.status] ?? c.status}
          </span>
          <span className="text-xs text-slate-400 dark:text-slate-500">
            {new Date(c.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>
    </Link>
  )
}

export default function DoctorPage() {
  const { data, isLoading, error } = useQuery<Case[]>({
    queryKey: ['cases'],
    queryFn: () => api.get<Case[]>('/api/cases').then((r) => r.data),
    refetchInterval: (query) =>
      query.state.data?.some((c) => c.status !== 'complete' && c.status !== 'failed' && c.status !== 'enqueue_failed')
        ? 2000
        : false,
  })

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Active Cases
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Diagnostic reasoning queue
          </p>
        </div>
        <Link
          href="/nurse"
          className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-md transition-colors"
        >
          New Case
        </Link>
      </div>

      {isLoading && (
        <div className="space-y-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">
          Failed to load cases. The API may be unavailable.
        </div>
      )}

      {!isLoading && !error && data && data.length === 0 && <EmptyState />}

      {!isLoading && !error && data && data.length > 0 && (
        <div className="space-y-2">
          {data.map((c) => (
            <CaseCard key={c.case_id} c={c} />
          ))}
        </div>
      )}
    </div>
  )
}
