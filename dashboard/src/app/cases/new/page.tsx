'use client'

import { useCallback, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { Loader2, Upload } from 'lucide-react'
import { Stepper } from '@/components/ui/Stepper'
import { JsonEditor } from '@/components/ui/JsonEditor'
import { api } from '@/lib/api'

// ── FHIR helpers ────────────────────────────────────────────────────────────

interface FhirResource {
  resourceType?: string
  name?: Array<{ text?: string; family?: string; given?: string[] }>
  period?: { start?: string }
  category?: Array<{ coding?: Array<{ code?: string }> }>
  code?: { text?: string; coding?: Array<{ display?: string }> }
}

interface FhirBundle {
  resourceType?: string
  entry?: Array<{ resource?: FhirResource }>
}

interface PatientSummary {
  patientName: string
  encounterId: string
  encounterDate: string
  chiefComplaint: string
  resourceCount: number
}

function summariseBundle(bundle: FhirBundle): PatientSummary {
  const entries = bundle.entry ?? []
  let patientName = 'Not detected'
  const encounterId = 'Not detected'
  let encounterDate = 'Not detected'
  let chiefComplaint = 'Not detected'

  for (const entry of entries) {
    const res = entry?.resource
    if (!res) continue

    if (res.resourceType === 'Patient' && patientName === 'Not detected') {
      const n = res.name?.[0]
      if (n?.text) patientName = n.text
      else if (n?.family) {
        const given = n.given?.join(' ') ?? ''
        patientName = [given, n.family].filter(Boolean).join(' ')
      }
    }

    if (res.resourceType === 'Encounter' && encounterDate === 'Not detected') {
      if (res.period?.start) {
        encounterDate = new Date(res.period.start).toLocaleString()
      }
    }

    if (res.resourceType === 'Condition' && chiefComplaint === 'Not detected') {
      const isChiefComplaint = res.category?.some((cat) =>
        cat.coding?.some((c) => c.code === 'chief-complaint')
      )
      if (isChiefComplaint || chiefComplaint === 'Not detected') {
        chiefComplaint =
          res.code?.text ??
          res.code?.coding?.[0]?.display ??
          'Not detected'
      }
    }
  }

  return { patientName, encounterId, encounterDate, chiefComplaint, resourceCount: entries.length }
}

// ── API call ─────────────────────────────────────────────────────────────────

interface CreateCaseResponse {
  case_id: string
}

async function postCase(fhir_bundle: unknown): Promise<CreateCaseResponse> {
  const { data } = await api.post<CreateCaseResponse>('/cases', { fhir_bundle })
  return data
}

// ── Step panels ───────────────────────────────────────────────────────────────

const STEPS = ['FHIR Bundle', 'Patient Summary', 'Confirm']

interface Step1Props {
  rawJson: string
  setRawJson: (v: string) => void
  onValidJson: (parsed: unknown) => void
  onInvalidJson: () => void
  isValid: boolean
  onNext: () => void
}

function Step1({ rawJson, setRawJson, onValidJson, onInvalidJson, isValid, onNext }: Step1Props) {
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = (evt) => {
        const text = evt.target?.result
        if (typeof text === 'string') setRawJson(text)
      }
      reader.readAsText(file)
      // reset so the same file can be re-selected
      e.target.value = ''
    },
    [setRawJson]
  )

  return (
    <div className="flex flex-col gap-4">
      <JsonEditor
        label="FHIR Bundle JSON"
        value={rawJson}
        onChange={setRawJson}
        onValidJson={onValidJson}
        onInvalidJson={onInvalidJson}
      />

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        >
          <Upload size={14} aria-hidden="true" />
          Upload .json file
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".json"
          onChange={handleFile}
          className="sr-only"
          aria-label="Upload FHIR bundle JSON file"
        />
      </div>

      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={onNext}
          disabled={!isValid}
          className="px-6 py-2 text-sm font-semibold rounded-md bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  )
}

interface Step2Props {
  summary: PatientSummary
  onBack: () => void
  onNext: () => void
}

function Step2({ summary, onBack, onNext }: Step2Props) {
  const rows: [string, string][] = [
    ['Patient', summary.patientName],
    ['Chief complaint', summary.chiefComplaint],
    ['Encounter date', summary.encounterDate],
    ['Resources in bundle', String(summary.resourceCount)],
  ]

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
        Patient Summary
      </h2>
      <dl className="divide-y divide-slate-100 dark:divide-slate-800 rounded-md border border-slate-200 dark:border-slate-700">
        {rows.map(([term, detail]) => (
          <div key={term} className="flex items-baseline px-4 py-3 gap-4">
            <dt className="w-44 flex-shrink-0 text-xs font-medium text-slate-500 dark:text-slate-400">
              {term}
            </dt>
            <dd
              className={`text-sm ${
                detail === 'Not detected'
                  ? 'text-slate-400 dark:text-slate-500 italic'
                  : 'text-slate-900 dark:text-slate-100'
              }`}
            >
              {detail}
            </dd>
          </div>
        ))}
      </dl>

      <div className="flex justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="px-5 py-2 text-sm font-medium rounded-md border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onNext}
          className="px-6 py-2 text-sm font-semibold rounded-md bg-emerald-500 text-white hover:bg-emerald-600 transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  )
}

interface Step3Props {
  summary: PatientSummary
  onBack: () => void
  onSubmit: () => void
  isPending: boolean
  error: string | null
}

function Step3({ summary, onBack, onSubmit, isPending, error }: Step3Props) {
  const rows: [string, string][] = [
    ['Patient', summary.patientName],
    ['Encounter date', summary.encounterDate],
    ['Resources in bundle', String(summary.resourceCount)],
  ]

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
        Confirm Submission
      </h2>

      <dl className="divide-y divide-slate-100 dark:divide-slate-800 rounded-md border border-slate-200 dark:border-slate-700">
        {rows.map(([term, detail]) => (
          <div key={term} className="flex items-baseline px-4 py-3 gap-4">
            <dt className="w-44 flex-shrink-0 text-xs font-medium text-slate-500 dark:text-slate-400">
              {term}
            </dt>
            <dd
              className={`text-sm ${
                detail === 'Not detected'
                  ? 'text-slate-400 dark:text-slate-500 italic'
                  : 'text-slate-900 dark:text-slate-100'
              }`}
            >
              {detail}
            </dd>
          </div>
        ))}
      </dl>

      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950 px-4 py-3 text-sm text-red-700 dark:text-red-300"
        >
          <span className="font-semibold">Error:</span>
          <span>{error}</span>
        </div>
      )}

      <div className="flex flex-col gap-2 pt-2">
        <button
          type="button"
          onClick={onSubmit}
          disabled={isPending}
          className="relative w-full flex items-center justify-center gap-2 px-6 py-2.5 text-sm font-semibold rounded-md bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          aria-busy={isPending}
        >
          {isPending && <Loader2 size={15} className="animate-spin" aria-hidden="true" />}
          {isPending ? 'Submitting…' : 'Submit Case'}
        </button>
        <button
          type="button"
          onClick={onBack}
          disabled={isPending}
          className="px-5 py-2 text-sm font-medium rounded-md border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50 transition-colors"
        >
          Back
        </button>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function NewCasePage() {
  const router = useRouter()
  const [step, setStep] = useState(0)
  const [rawJson, setRawJson] = useState('')
  const [parsedBundle, setParsedBundle] = useState<unknown>(null)
  const [isJsonValid, setIsJsonValid] = useState(false)
  const [summary, setSummary] = useState<PatientSummary | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const { mutate, isPending } = useMutation({
    mutationFn: (bundle: unknown) => postCase(bundle),
    onSuccess: (data) => {
      router.push(`/cases/${data.case_id}`)
    },
    onError: (err: Error) => {
      setSubmitError(err.message ?? 'Submission failed')
    },
  })

  const handleValidJson = useCallback((parsed: unknown) => {
    setParsedBundle(parsed)
    setIsJsonValid(true)
  }, [])

  const handleInvalidJson = useCallback(() => {
    setParsedBundle(null)
    setIsJsonValid(false)
  }, [])

  const goToStep2 = useCallback(() => {
    if (!parsedBundle) return
    const s = summariseBundle(parsedBundle as FhirBundle)
    setSummary(s)
    setStep(1)
  }, [parsedBundle])

  const goToStep3 = useCallback(() => setStep(2), [])
  const goBack = useCallback(() => setStep((s) => Math.max(0, s - 1)), [])

  const handleSubmit = useCallback(() => {
    setSubmitError(null)
    mutate(parsedBundle)
  }, [mutate, parsedBundle])

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-6">New Case</h1>

      <div className="mb-8">
        <Stepper steps={STEPS} currentStep={step} />
      </div>

      <div className="rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
        {step === 0 && (
          <Step1
            rawJson={rawJson}
            setRawJson={setRawJson}
            onValidJson={handleValidJson}
            onInvalidJson={handleInvalidJson}
            isValid={isJsonValid}
            onNext={goToStep2}
          />
        )}

        {step === 1 && summary && (
          <Step2 summary={summary} onBack={goBack} onNext={goToStep3} />
        )}

        {step === 2 && summary && (
          <Step3
            summary={summary}
            onBack={goBack}
            onSubmit={handleSubmit}
            isPending={isPending}
            error={submitError}
          />
        )}
      </div>
    </div>
  )
}
