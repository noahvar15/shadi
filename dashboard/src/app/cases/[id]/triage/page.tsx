'use client'

import { use } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, ChevronLeft } from 'lucide-react'
import Link from 'next/link'
import { api } from '@/lib/api'
import { TriageDoc } from '@/components/report/TriageDoc'

interface CaseSummary {
  case_id: string
  patient_id: string
  patient_name?: string
  status: string
  created_at: string
  chief_complaint?: string
}

export default function TriagePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)

  const { data, isLoading, error } = useQuery<CaseSummary>({
    queryKey: ['case', id],
    queryFn: () => api.get<CaseSummary>(`/api/cases/${id}`).then((r) => r.data),
  })

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-6">
        <Link
          href="/doctor"
          className="text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] flex items-center gap-1 transition-colors"
        >
          <ChevronLeft size={14} /> Cases
        </Link>
        {data && (
          <>
            <span className="text-[var(--foreground-muted)] text-sm">/</span>
            <Link
              href={`/cases/${id}`}
              className="text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors font-mono"
            >
              {id}
            </Link>
            <span className="text-[var(--foreground-muted)] text-sm">/</span>
            <span className="text-sm text-[var(--foreground)]">Triage Note</span>
          </>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="animate-spin text-emerald-500" size={28} />
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">
          Failed to load triage note. The case may not exist.
        </div>
      )}

      {data && (
        <>
          <TriageDoc
            chiefComplaint={data.chief_complaint ?? ''}
            patientId={data.patient_id}
            createdAt={data.created_at}
            patientName={data.patient_name}
          />

          {/* Link to full diagnostic report if complete */}
          {data.status === 'complete' && (
            <div className="mt-4 flex justify-end">
              <Link
                href={`/cases/${id}`}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-lg transition-colors"
              >
                View Diagnostic Report →
              </Link>
            </div>
          )}
        </>
      )}
    </div>
  )
}
