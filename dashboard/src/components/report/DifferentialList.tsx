'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { DiagnosisCandidate } from '@/types/report'

interface DifferentialListProps {
  diagnoses: DiagnosisCandidate[]
  onCitationClick: (d: DiagnosisCandidate) => void
}

function confidenceBarClass(confidence: number): string {
  if (confidence > 0.8) return 'bg-emerald-500'
  if (confidence >= 0.5) return 'bg-amber-400'
  return 'bg-slate-400 dark:bg-red-600'
}

function confidenceTextClass(confidence: number): string {
  if (confidence > 0.8) return 'text-emerald-700 dark:text-emerald-400'
  if (confidence >= 0.5) return 'text-amber-700 dark:text-amber-400'
  return 'text-slate-500 dark:text-slate-400'
}

function rankBadgeClass(rank: number): string {
  if (rank === 1) return 'bg-emerald-500 text-white'
  if (rank === 2) return 'bg-slate-500 text-white'
  return 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
}

interface DiagnosisCardProps {
  diagnosis: DiagnosisCandidate
  rank: number
  onCitationClick: (d: DiagnosisCandidate) => void
}

function DiagnosisCard({ diagnosis, rank, onCitationClick }: DiagnosisCardProps) {
  const [expanded, setExpanded] = useState(false)
  const normalizedConfidence = Math.max(0, Math.min(1, diagnosis.confidence))
  const pct = Math.round(normalizedConfidence * 100)

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-md overflow-hidden bg-white dark:bg-slate-900">
      {/* Header row */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center gap-3 mb-2">
          {/* Rank badge */}
          <span
            className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-xs font-bold flex-shrink-0 ${rankBadgeClass(rank)}`}
            aria-label={`Rank ${rank}`}
          >
            {rank}
          </span>

          {/* Diagnosis name */}
          <span className="font-semibold text-slate-900 dark:text-slate-100 flex-1 leading-tight">
            {diagnosis.diagnosis}
          </span>

          {/* ICD code */}
          {diagnosis.icd_code && (
            <span className="font-mono text-xs text-slate-500 dark:text-slate-400 flex-shrink-0">
              {diagnosis.icd_code}
            </span>
          )}

          {/* Confidence % */}
          <span className={`text-sm font-semibold font-mono flex-shrink-0 ${confidenceTextClass(normalizedConfidence)}`}>
            {pct}%
          </span>

          {/* Expand toggle */}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 dark:text-slate-500 transition-colors flex-shrink-0"
            aria-label={expanded ? 'Collapse details' : 'Expand details'}
            aria-expanded={expanded}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Confidence bar */}
        <div
          className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Confidence: ${pct}%`}
        >
          <div
            className={`h-full rounded-full transition-all duration-300 ${confidenceBarClass(normalizedConfidence)}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-slate-100 dark:border-slate-800 space-y-4">
          {/* Reasoning */}
          {diagnosis.reasoning_trace.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">
                Reasoning
              </h4>
              <ul className="space-y-1 list-disc list-inside text-sm text-slate-700 dark:text-slate-300">
                {diagnosis.reasoning_trace.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Next steps */}
          {diagnosis.next_steps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">
                Next Steps
              </h4>
              <ul className="space-y-1 list-disc list-inside text-sm text-slate-700 dark:text-slate-300">
                {diagnosis.next_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Citations button */}
          <button
            onClick={() => onCitationClick(diagnosis)}
            className="mt-1 px-3 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
          >
            View Citations ({diagnosis.supporting_evidence.length})
          </button>
        </div>
      )}
    </div>
  )
}

export function DifferentialList({ diagnoses, onCitationClick }: DifferentialListProps) {
  if (diagnoses.length === 0) {
    return (
      <p className="text-sm text-slate-400 dark:text-slate-500">No diagnoses available.</p>
    )
  }

  return (
    <section aria-label="Differential diagnoses" className="space-y-3">
      {diagnoses.map((diagnosis, idx) => (
        <DiagnosisCard
          key={diagnosis.icd_code ?? diagnosis.diagnosis}
          diagnosis={diagnosis}
          rank={idx + 1}
          onCitationClick={onCitationClick}
        />
      ))}
    </section>
  )
}
