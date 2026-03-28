'use client'

import { use, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { DifferentialReport, DiagnosisCandidate } from '@/types/report'
import { SafetyBanner } from '@/components/report/SafetyBanner'
import { DebateSummary } from '@/components/report/DebateSummary'
import { DifferentialList } from '@/components/report/DifferentialList'
import { CitationPanel } from '@/components/report/CitationPanel'

function statusLabel(status: DifferentialReport['status']): string {
  switch (status) {
    case 'queued':
      return 'Queued…'
    case 'running':
      return 'Running specialists…'
    default:
      return 'Synthesizing…'
  }
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

  const { data: report, error, isLoading } = useQuery<DifferentialReport, Error>({
    queryKey: ['report', id],
    queryFn: () => api.get<DifferentialReport>(`/reports/${id}`).then((r) => r.data),
    refetchInterval: (query) =>
      query.state.data?.status === 'complete' ? false : 2000,
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

  if (isInProgress) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        {/* Indeterminate progress strip */}
        <div className="h-1 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
          <div className="h-full w-1/3 bg-emerald-500 rounded-full animate-pulse" />
        </div>

        {/* Status text */}
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {report ? statusLabel(report.status) : 'Loading…'}
        </p>

        {/* Skeleton cards */}
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="animate-pulse bg-slate-200 dark:bg-slate-800 rounded h-24"
            aria-hidden="true"
          />
        ))}
      </div>
    )
  }

  return (
    <>
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
