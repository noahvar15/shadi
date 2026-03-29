'use client'

import { X } from 'lucide-react'
import type { Evidence } from '@/types/report'

interface CitationPanelProps {
  evidence: Evidence[]
  isOpen: boolean
  onClose: () => void
  diagnosisName: string
}

function parsePubMed(source: string): { pmid: string; label: string } | null {
  const prefix = 'PubMed:'
  if (source.startsWith(prefix)) {
    const pmid = source.slice(prefix.length).trim()
    return { pmid, label: `PubMed: ${pmid}` }
  }
  return null
}

export function CitationPanel({ evidence, isOpen, onClose, diagnosisName }: CitationPanelProps) {
  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/40 z-40 transition-opacity duration-200 ${
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Drawer */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Citations for ${diagnosisName}`}
        className={`fixed top-0 right-0 h-full w-full max-w-md bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-700 z-50 flex flex-col transition-transform duration-300 ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-700 flex-shrink-0">
          <h2 className="font-semibold text-slate-900 dark:text-slate-100 text-sm leading-snug max-w-[85%]">
            {diagnosisName || 'Citations'}
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors"
            aria-label="Close citation panel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {evidence.length === 0 ? (
            <p className="text-sm text-slate-400 dark:text-slate-500">No citations available.</p>
          ) : (
            evidence.map((ev, idx) => {
              const pubmed = parsePubMed(ev.source)
              const relevancePct = Math.max(0, Math.min(100, Math.round(ev.relevance_score * 100)))
              return (
                <div key={idx} className="space-y-2">
                  {/* Source */}
                  <div className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    {pubmed ? (
                      <a
                        href={`https://pubmed.ncbi.nlm.nih.gov/${pubmed.pmid}/`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-600 dark:text-emerald-400 hover:underline"
                      >
                        {pubmed.label}
                      </a>
                    ) : (
                      ev.source
                    )}
                  </div>

                  {/* Excerpt */}
                  <blockquote className="border-l-2 border-slate-200 dark:border-slate-700 pl-3 text-sm text-slate-600 dark:text-slate-400 italic">
                    {ev.excerpt}
                  </blockquote>

                  {/* Relevance bar */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
                      <span>Relevance</span>
                      <span>{relevancePct}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                        style={{ width: `${relevancePct}%` }}
                        role="progressbar"
                        aria-valuenow={relevancePct}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      />
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </aside>
    </>
  )
}
