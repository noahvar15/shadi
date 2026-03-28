'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Stethoscope, FolderPlus } from 'lucide-react'
import { api } from '@/lib/api'

interface Case {
  case_id: string
  patient_id: string
  status: 'complete' | 'running' | 'queued'
  created_at: string
}

const STATUS_STYLES: Record<Case['status'], string> = {
  complete: 'bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  running:  'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  queued:   'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400',
}

function SkeletonCard() {
  return (
    <div className="bg-[var(--surface)] rounded-[1rem] shadow-card p-4">
      <div className="animate-pulse space-y-2">
        <div className="h-3.5 bg-slate-200 dark:bg-slate-700 rounded w-2/5" />
        <div className="h-3 bg-slate-100 dark:bg-slate-700/60 rounded w-1/4" />
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-32 text-center">
      <div className="h-16 w-16 rounded-2xl bg-violet-50 dark:bg-violet-900/20 flex items-center justify-center mb-5">
        <Stethoscope className="w-7 h-7 text-violet-500 dark:text-violet-400" />
      </div>
      <h2 className="text-base font-semibold text-[var(--foreground)] mb-1">
        No cases yet
      </h2>
      <p className="text-sm text-[var(--foreground-muted)] mb-6 max-w-xs">
        Submit a new patient case to begin diagnostic reasoning.
      </p>
      <Link
        href="/cases/new"
        className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 dark:bg-violet-500 dark:hover:bg-violet-600 text-white text-sm font-medium rounded-lg transition-colors"
      >
        <FolderPlus size={15} />
        New Case
      </Link>
    </div>
  )
}

function CaseCard({ c }: { c: Case }) {
  return (
    <Link
      href={`/cases/${c.case_id}`}
      className="block p-4 bg-[var(--surface)] rounded-[1rem] shadow-card hover:shadow-card-hover transition-shadow"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-mono font-medium text-[var(--foreground)] truncate">
            {c.case_id}
          </p>
          <p className="text-xs text-[var(--foreground-muted)] mt-0.5">
            Patient {c.patient_id}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[c.status]}`}>
            {c.status}
          </span>
          <span className="text-xs text-[var(--foreground-muted)] font-mono">
            {new Date(c.created_at).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
            })}
          </span>
        </div>
      </div>
    </Link>
  )
}

export default function HomePage() {
  const { data, isLoading, error } = useQuery<Case[]>({
    queryKey: ['cases'],
    queryFn: () => api.get<Case[]>('/cases').then((r) => r.data),
  })

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[var(--foreground)]">Active Cases</h1>
          <p className="text-sm text-[var(--foreground-muted)] mt-0.5">
            Diagnostic reasoning queue
          </p>
        </div>
        <Link
          href="/cases/new"
          className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 dark:bg-violet-500 dark:hover:bg-violet-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <FolderPlus size={15} />
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
        <div className="p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800/50 text-red-600 dark:text-red-400 text-sm">
          Failed to load cases. The API may be unavailable.
        </div>
      )}

      {!isLoading && !error && data && data.length === 0 && <EmptyState />}

      {!isLoading && !error && data && data.length > 0 && (
        <div className="space-y-2.5">
          {data.map((c) => (
            <CaseCard key={c.case_id} c={c} />
          ))}
        </div>
      )}
    </div>
  )
}
