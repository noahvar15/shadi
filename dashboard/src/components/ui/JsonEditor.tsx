'use client'

import { useEffect, useReducer, useRef } from 'react'
import { CheckCircle, XCircle } from 'lucide-react'

interface FhirBundle {
  resourceType?: string
  entry?: Array<{
    resource?: {
      resourceType?: string
      name?: Array<{ text?: string; family?: string; given?: string[] }>
      period?: { start?: string }
    }
  }>
}

function extractBundleInfo(parsed: unknown): string {
  const bundle = parsed as FhirBundle
  if (bundle?.resourceType !== 'Bundle' || !Array.isArray(bundle.entry)) {
    return 'Valid JSON'
  }

  let patientName: string | null = null
  let encounterDate: string | null = null

  for (const entry of bundle.entry) {
    const res = entry?.resource
    if (!res) continue

    if (res.resourceType === 'Patient' && !patientName) {
      const nameEntry = res.name?.[0]
      if (nameEntry?.text) {
        patientName = nameEntry.text
      } else if (nameEntry?.family) {
        const given = nameEntry.given?.join(' ') ?? ''
        patientName = [given, nameEntry.family].filter(Boolean).join(' ')
      }
    }

    if (res.resourceType === 'Encounter' && !encounterDate) {
      const start = res.period?.start
      if (start) {
        encounterDate = new Date(start).toLocaleDateString()
      }
    }
  }

  const parts: string[] = []
  if (patientName) parts.push(`Patient: ${patientName}`)
  if (encounterDate) parts.push(`Encounter: ${encounterDate}`)

  return parts.length > 0 ? `Valid JSON — ${parts.join(', ')}` : 'Valid JSON'
}

type ValidationState =
  | { kind: 'empty' }
  | { kind: 'valid'; message: string }
  | { kind: 'invalid'; message: string }

export interface JsonEditorProps {
  value: string
  onChange: (v: string) => void
  onValidJson: (parsed: unknown) => void
  onInvalidJson: () => void
  label?: string
}

export function JsonEditor({
  value,
  onChange,
  onValidJson,
  onInvalidJson,
  label,
}: JsonEditorProps) {
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [validation, setValidation] = useReducer(
    (_: ValidationState, next: ValidationState) => next,
    { kind: 'empty' } as ValidationState
  )

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    if (value.trim() === '') {
      setValidation({ kind: 'empty' })
      onInvalidJson()
      return
    }

    debounceRef.current = setTimeout(() => {
      try {
        const parsed = JSON.parse(value)
        const message = extractBundleInfo(parsed)
        setValidation({ kind: 'valid', message })
        onValidJson(parsed)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Invalid JSON'
        setValidation({ kind: 'invalid', message })
        onInvalidJson()
      }
    }, 300)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</label>
      )}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={10}
        spellCheck={false}
        className="w-full font-mono text-sm px-3 py-2 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent resize-y"
        placeholder="Paste FHIR bundle JSON here..."
        aria-describedby={validation.kind !== 'empty' ? 'json-validation-msg' : undefined}
        aria-invalid={validation.kind === 'invalid' || undefined}
      />
      {validation.kind === 'valid' && (
        <p
          id="json-validation-msg"
          className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400"
          role="status"
          aria-live="polite"
        >
          <CheckCircle size={13} aria-hidden="true" />
          {validation.message}
        </p>
      )}
      {validation.kind === 'invalid' && (
        <p
          id="json-validation-msg"
          className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400"
          role="alert"
          aria-live="assertive"
        >
          <XCircle size={13} aria-hidden="true" />
          {validation.message}
        </p>
      )}
    </div>
  )
}
