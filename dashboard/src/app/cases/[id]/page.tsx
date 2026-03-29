'use client'

import { use, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Loader2, ChevronLeft, ThumbsUp, ThumbsDown } from 'lucide-react'
import Link from 'next/link'
import { api } from '@/lib/api'
import type { DifferentialReport, DiagnosisCandidate } from '@/types/report'
import { SafetyBanner } from '@/components/report/SafetyBanner'
import { DebateSummary } from '@/components/report/DebateSummary'
import { DifferentialList } from '@/components/report/DifferentialList'
import { CitationPanel } from '@/components/report/CitationPanel'

function StatusText({ status }: { status: DifferentialReport['status'] | undefined }) {
  if (!status || status === 'queued') {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        {status ? 'Queued — waiting for pipeline slot\u2026' : 'Loading\u2026'}
      </p>
    )
  }
  if (status === 'running') {
    return (
      <p className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        Running specialist agents\u2026
      </p>
    )
  }
  return (
    <p className="text-sm text-slate-500 dark:text-slate-400">
      Synthesizing consensus\u2026
    </p>
  )
}

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [selectedDiagnosis, setSelectedDiagnosis] = useState<DiagnosisCandidate | null>(null)
  const [vote, setVote] = useState<'up' | 'down' | null>(null)

  const feedbackMutation = useMutation({
    mutationFn: (v: 'up' | 'down' | null) =>
      api.post(`/api/cases/${id}/feedback`, { vote: v }).then((r) => r.data),
    onSuccess: (_data, v) => {
      setVote(v)
    },
  })

  function handleVote(v: 'up' | 'down') {
    // Clicking the active choice clears it; clicking the other switches.
    const next = vote === v ? null : v
    feedbackMutation.mutate(next)
  }

  // TanStack Query handles cleanup on unmount automatically — no manual teardown needed.
  const { data: report, error, isLoading } = useQuery<DifferentialReport, Error>({
    queryKey: ['report', id],
    queryFn: () => api.get<DifferentialReport>(`/api/reports/${id}`).then((r) => r.data),
    // Stop polling once terminal (complete or failed); keep polling while queued/running.
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'complete' || s === 'failed' ? false : 2000
    },
  })

  const isInProgress =
    isLoading || !report || report.status === 'queued' || report.status === 'running'

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-md p-5">
          <p className="text-red-700 dark:text-red-300 font-medium text-sm">
            Failed to load report
          </p>
          <p className="text-red-600 dark:text-red-400 text-sm mt-1">{error.message}</p>
        </div>
      </div>
    )
  }

  if (report?.status === 'failed') {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center gap-2 px-6 py-3 border-b border-[var(--border)] -mx-4 -mt-8 mb-8">
          <Link href="/doctor" className="text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] flex items-center gap-1 transition-colors">
            <ChevronLeft size={14} /> Cases
          </Link>
        </div>
        <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-md p-5">
          <p className="text-red-700 dark:text-red-300 font-medium text-sm">
            Diagnostic pipeline failed
          </p>
          <p className="text-red-600 dark:text-red-400 text-sm mt-1">
            The agent pipeline encountered an error processing this case. Please try resubmitting.
          </p>
        </div>
      </div>
    )
  }

  if (isInProgress) {
    return (
      <>
        <div className="flex items-center gap-2 px-6 py-3 border-b border-[var(--border)]">
          <Link href="/doctor" className="text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] flex items-center gap-1 transition-colors">
            <ChevronLeft size={14} /> Cases
          </Link>
        </div>

        {/* Full-width indeterminate progress bar — sits at very top of page */}
        <div className="w-full h-1 bg-slate-200 dark:bg-slate-800 overflow-hidden">
          <div className="h-full bg-emerald-500 animate-[progressBar_1.5s_ease-in-out_infinite]" />
        </div>

        <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
          <StatusText status={report?.status} />

          {/* Skeleton cards */}
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="animate-pulse bg-slate-200 dark:bg-slate-800 rounded h-24"
              aria-hidden="true"
            />
          ))}
        </div>
      </>
    )
  }

  return (
    <>
      <div className="flex items-center gap-2 px-6 py-3 border-b border-[var(--border)]">
        <Link href="/doctor" className="text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] flex items-center gap-1 transition-colors">
          <ChevronLeft size={14} /> Cases
        </Link>
      </div>

      <SafetyBanner vetoedRecommendations={report.vetoed_recommendations} />

      <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Page header */}
        <header className="space-y-1">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Diagnostic Report
          </h1>
          <div className="flex items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
            <span>
              Case{' '}
              <span className="font-mono text-slate-700 dark:text-slate-300">{report.case_id}</span>
            </span>
            {report.completed_at && (
              <span>Completed {formatTimestamp(report.completed_at)}</span>
            )}
          </div>
        </header>

        <DebateSummary
          consensusLevel={report.consensus_level}
          divergentAgents={report.divergent_agents}
        />

        {/* Doctor feedback — toggleable thumbs up / down on the triage note */}
        <div className="flex items-center gap-4 p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl">
          <div className="flex-1">
            <p className="text-sm font-semibold text-[var(--foreground)]">
              Triage Assessment
            </p>
            <p className="text-xs text-[var(--foreground-muted)] mt-0.5">
              {vote === 'up'
                ? 'Marked as accurate — click again to clear.'
                : vote === 'down'
                ? 'Flagged for review — click again to clear.'
                : 'Was the triage note accurate and complete?'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleVote('up')}
              disabled={feedbackMutation.isPending}
              aria-label="Triage accurate"
              aria-pressed={vote === 'up'}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${
                vote === 'up'
                  ? 'bg-emerald-500 border-emerald-500 text-white'
                  : 'border-[var(--border)] text-[var(--foreground-muted)] hover:border-emerald-400 hover:text-emerald-600 dark:hover:text-emerald-400'
              }`}
            >
              <ThumbsUp size={14} strokeWidth={2} />
              Accurate
            </button>
            <button
              onClick={() => handleVote('down')}
              disabled={feedbackMutation.isPending}
              aria-label="Triage needs review"
              aria-pressed={vote === 'down'}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${
                vote === 'down'
                  ? 'bg-red-500 border-red-500 text-white'
                  : 'border-[var(--border)] text-[var(--foreground-muted)] hover:border-red-400 hover:text-red-500'
              }`}
            >
              <ThumbsDown size={14} strokeWidth={2} />
              Review
            </button>
          </div>
        </div>

        <DifferentialList
          diagnoses={report.top_diagnoses}
          onCitationClick={setSelectedDiagnosis}
        />
      </div>

      <CitationPanel
        evidence={selectedDiagnosis?.supporting_evidence ?? []}
        isOpen={!!selectedDiagnosis}
        onClose={() => setSelectedDiagnosis(null)}
        diagnosisName={selectedDiagnosis?.diagnosis ?? ''}
      />
    </>
  )
}
