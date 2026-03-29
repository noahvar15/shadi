'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import Link from 'next/link'
import { Loader2, ChevronLeft } from 'lucide-react'
import { api } from '@/lib/api'

interface CreateCasePayload {
  chief_complaint: string
  patient_id?: string
}

interface CreateCaseResponse {
  case_id: string
}

export default function NursePage() {
  const router = useRouter()
  const [chiefComplaint, setChiefComplaint] = useState('')
  const [patientStubId, setPatientStubId] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  const { mutate, isPending, error } = useMutation<CreateCaseResponse, Error, CreateCasePayload>({
    mutationFn: (payload) =>
      api.post<CreateCaseResponse>('/api/cases', payload).then((r) => r.data),
    onSuccess: (data) => {
      router.push(`/cases/${data.case_id}`)
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setValidationError(null)

    if (chiefComplaint.trim().length < 10) {
      setValidationError('Chief complaint must be at least 10 characters.')
      return
    }

    const payload: CreateCasePayload = {
      chief_complaint: chiefComplaint.trim(),
      ...(patientStubId.trim() ? { patient_id: patientStubId.trim() } : {}),
    }

    mutate(payload)
  }

  return (
    <div className="max-w-lg mx-auto px-6 py-10">
      <div className="mb-6">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
        >
          <ChevronLeft size={14} />
          Back
        </Link>
        <h1 className="text-xl font-bold text-[var(--foreground)] mt-4">Triage Intake</h1>
        <p className="text-sm text-[var(--foreground-muted)] mt-1">
          Enter patient triage information
        </p>
      </div>

      <div className="bg-[var(--surface)] rounded-card shadow-card p-6 space-y-5">
        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          <div className="space-y-1.5">
            <label
              htmlFor="chief_complaint"
              className="block text-sm font-medium text-[var(--foreground)]"
            >
              Chief Complaint <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <textarea
              id="chief_complaint"
              name="chief_complaint"
              rows={4}
              required
              minLength={10}
              placeholder="e.g. chest pain radiating to left arm, onset 2 hours ago"
              value={chiefComplaint}
              onChange={(e) => {
                setChiefComplaint(e.target.value)
                if (validationError) setValidationError(null)
              }}
              className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition resize-none"
            />
            {validationError && (
              <p className="text-xs text-red-500 dark:text-red-400" role="alert">
                {validationError}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="patient_stub_id"
              className="block text-sm font-medium text-[var(--foreground)]"
            >
              Patient ID{' '}
              <span className="text-[var(--foreground-muted)] font-normal">(optional)</span>
            </label>
            <input
              id="patient_stub_id"
              name="patient_stub_id"
              type="text"
              placeholder="e.g. PT-2024-001 — leave blank to auto-generate"
              value={patientStubId}
              onChange={(e) => setPatientStubId(e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] placeholder:font-sans focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition"
            />
          </div>

          {error && (
            <div
              role="alert"
              className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm"
            >
              Failed to submit case. Please try again.
            </div>
          )}

          <button
            type="submit"
            disabled={isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
          >
            {isPending ? (
              <>
                <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                Submitting…
              </>
            ) : (
              'Submit Case'
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
