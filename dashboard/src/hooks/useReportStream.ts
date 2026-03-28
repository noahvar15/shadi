'use client'

import { useEffect, useRef, useState } from 'react'
import type { DifferentialReport } from '@/types/report'

interface StreamState {
  status: 'connecting' | 'streaming' | 'complete' | 'error'
  currentStep: string | null
  report: DifferentialReport | null
  error: string | null
}

/**
 * SSE hook for live report streaming via GET /reports/{id}/stream.
 *
 * Not yet wired to the report page — the backend SSE endpoint (GET /reports/{id}/stream)
 * is tracked in issue #33 (Emmanuel's track). Switch from polling to this hook
 * once that endpoint is available.
 *
 * Expected SSE events:
 *   { event: "progress", data: "step_name" }
 *   { event: "complete", data: DifferentialReport (JSON) }
 *   { event: "error", data: "error message" }
 */
export function useReportStream(caseId: string, enabled = false): StreamState {
  const [state, setState] = useState<StreamState>({
    status: 'connecting',
    currentStep: null,
    report: null,
    error: null,
  })
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!enabled) return

    const url = `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/reports/${caseId}/stream`
    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('progress', (e) => {
      setState((prev) => ({ ...prev, status: 'streaming', currentStep: e.data }))
    })

    es.addEventListener('complete', (e) => {
      try {
        const report = JSON.parse(e.data) as DifferentialReport
        setState({ status: 'complete', currentStep: null, report, error: null })
      } catch {
        setState((prev) => ({ ...prev, status: 'error', error: 'Failed to parse report' }))
      }
      es.close()
    })

    es.addEventListener('error', () => {
      setState((prev) => ({ ...prev, status: 'error', error: 'Stream connection failed' }))
      es.close()
    })

    return () => {
      es.close()
      esRef.current = null
    }
  }, [caseId, enabled])

  return state
}
