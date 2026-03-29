'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation } from '@tanstack/react-query'
import { Loader2, ImagePlus, X } from 'lucide-react'
import { api } from '@/lib/api'

interface CreateCasePayload {
  chief_complaint: string
  patient_stub_id?: string
  patient_name?: string
}

interface CreateCaseResponse {
  case_id: string
}

const MENTAL_STATUS_OPTIONS = [
  { key: 'alert_oriented', label: 'Alert/Oriented' },
  { key: 'awake_confused', label: 'Awake/Confused' },
  { key: 'verbally_responsive', label: 'Verbally Responsive' },
  { key: 'responds_to_pain', label: 'Responds to Pain' },
  { key: 'aphasic', label: 'Aphasic' },
  { key: 'unresponsive', label: 'Unresponsive' },
]

const PMH_OPTIONS = [
  { key: 'htn', label: 'Hypertension (HTN)' },
  { key: 'heart_disease', label: 'Heart Disease' },
  { key: 'hiv', label: 'HIV' },
  { key: 'copd', label: 'COPD' },
  { key: 'stroke', label: 'Stroke/CVA' },
  { key: 'cancer', label: 'Cancer' },
  { key: 'asthma', label: 'Asthma' },
  { key: 'diabetes', label: 'Diabetes' },
  { key: 'seizures', label: 'Seizures' },
]

const SECTION_HEADER =
  'text-xs font-semibold uppercase tracking-wider text-[var(--foreground-muted)] border-b border-[var(--border)] pb-1 mb-3'

const INPUT_BASE =
  'w-full px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition'

const CARD = 'bg-[var(--surface)] rounded-card shadow-card p-5'

const LABEL = 'block text-sm font-medium text-[var(--foreground)] mb-1'

export default function NursePage() {
  const router = useRouter()

  // Patient info
  const [patientName, setPatientName] = useState('')
  const [patientStubId, setPatientStubId] = useState('')
  const [dateTime, setDateTime] = useState('')

  // Chief complaint
  const [chiefComplaint, setChiefComplaint] = useState('')
  const [narrative, setNarrative] = useState('')

  // Vitals
  const [bpSys, setBpSys] = useState('')
  const [bpDia, setBpDia] = useState('')
  const [heartRate, setHeartRate] = useState('')
  const [respRate, setRespRate] = useState('')
  const [temp, setTemp] = useState('')
  const [o2sat, setO2sat] = useState('')
  const [pain, setPain] = useState(0)

  // Mental status
  const [mentalStatus, setMentalStatus] = useState<Record<string, boolean>>({})

  // PMH
  const [pmh, setPmh] = useState<Record<string, boolean>>({})
  const [pmhOther, setPmhOther] = useState(false)
  const [pmhOtherText, setPmhOtherText] = useState('')

  // Clinical images
  const [images, setImages] = useState<File[]>([])

  // Allergies / Medications
  const [noKnownAllergies, setNoKnownAllergies] = useState(false)
  const [allergies, setAllergies] = useState('')
  const [medications, setMedications] = useState('')

  // Session
  const [nurseName, setNurseName] = useState<string | null>(null)

  // Validation
  const [validationError, setValidationError] = useState<string | null>(null)

  useEffect(() => {
    setDateTime(new Date().toISOString().slice(0, 16))
    try {
      const raw = localStorage.getItem('shadi_session')
      if (raw) {
        const session = JSON.parse(raw)
        setNurseName(session.name ?? null)
      }
    } catch {
      // ignore
    }
  }, [])

  const { mutate, isPending, error: mutationError } = useMutation<
    CreateCaseResponse,
    Error,
    CreateCasePayload
  >({
    mutationFn: (payload) =>
      api.post<CreateCaseResponse>('/api/cases/intake', payload).then((r) => r.data),
    onSuccess: (data) => {
      router.push(`/cases/${data.case_id}`)
    },
  })

  function buildChiefComplaint(): string {
    const lines: string[] = []

    lines.push(`Chief Complaint: ${chiefComplaint.trim()}`)

    const vitalParts: string[] = []
    if (bpSys || bpDia) vitalParts.push(`BP ${bpSys || '?'}/${bpDia || '?'}`)
    if (heartRate) vitalParts.push(`HR ${heartRate}`)
    if (respRate) vitalParts.push(`RR ${respRate}`)
    if (temp) vitalParts.push(`Temp ${temp}°F`)
    if (o2sat) vitalParts.push(`O2 ${o2sat}%`)
    vitalParts.push(`Pain ${pain}/10`)
    lines.push(`Vitals: ${vitalParts.join(', ')}`)

    const mentalItems = MENTAL_STATUS_OPTIONS.filter((o) => mentalStatus[o.key]).map(
      (o) => o.label
    )
    if (mentalItems.length) lines.push(`Mental Status: ${mentalItems.join(', ')}`)

    const pmhItems = PMH_OPTIONS.filter((o) => pmh[o.key]).map((o) => o.label)
    if (pmhOther && pmhOtherText.trim()) pmhItems.push(pmhOtherText.trim())
    if (pmhItems.length) lines.push(`PMH: ${pmhItems.join(', ')}`)

    const allergyText = noKnownAllergies
      ? 'No Known Allergies'
      : allergies.trim() || 'Not reported'
    lines.push(`Allergies: ${allergyText}`)

    if (medications.trim()) lines.push(`Medications: ${medications.trim()}`)
    if (narrative.trim()) lines.push(`Narrative: ${narrative.trim()}`)
    if (images.length) lines.push(`Attachments: ${images.map((f) => f.name).join(', ')}`)

    return lines.join('\n')
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setValidationError(null)

    if (chiefComplaint.trim().length < 3) {
      setValidationError('Chief complaint is required.')
      return
    }

    const payload: CreateCasePayload = {
      chief_complaint: buildChiefComplaint(),
      ...(patientStubId.trim() ? { patient_stub_id: patientStubId.trim() } : {}),
      ...(patientName.trim() ? { patient_name: patientName.trim() } : {}),
    }

    mutate(payload)
  }

  return (
    <div className="max-w-3xl mx-auto px-6 pt-10 pb-4">
      <div className="mb-7">
        <h1 className="text-xl font-bold text-[var(--foreground)]">
          Triage Intake{nurseName ? ` — ${nurseName}` : ''}
        </h1>
        <p className="text-sm text-[var(--foreground-muted)] mt-1">
          Complete all applicable sections and submit to start diagnostic analysis
        </p>
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        {/* Section 1 — Patient Info */}
        <div className={CARD}>
          <h2 className={SECTION_HEADER}>Patient Information</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-1">
              <label htmlFor="patient_name" className={LABEL}>
                Patient Name <span className="text-red-500" aria-hidden="true">*</span>
              </label>
              <input
                id="patient_name"
                type="text"
                required
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                placeholder="Full name"
                className={INPUT_BASE}
              />
            </div>
            <div>
              <label htmlFor="patient_stub_id" className={LABEL}>
                Patient ID{' '}
                <span className="text-[var(--foreground-muted)] font-normal">(optional)</span>
              </label>
              <input
                id="patient_stub_id"
                type="text"
                value={patientStubId}
                onChange={(e) => setPatientStubId(e.target.value)}
                placeholder="e.g. PT-2024-001"
                className={`${INPUT_BASE} font-mono placeholder:font-sans`}
              />
            </div>
            <div>
              <label htmlFor="intake_datetime" className={LABEL}>
                Date / Time
              </label>
              <input
                id="intake_datetime"
                type="datetime-local"
                readOnly
                value={dateTime}
                className={`${INPUT_BASE} cursor-default`}
                tabIndex={-1}
              />
            </div>
          </div>
        </div>

        {/* Section 2 — Chief Complaint & Narrative */}
        <div className={CARD}>
          <h2 className={SECTION_HEADER}>Chief Complaint &amp; Narrative</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="chief_complaint" className={LABEL}>
                Chief Complaint <span className="text-red-500" aria-hidden="true">*</span>
              </label>
              <textarea
                id="chief_complaint"
                rows={3}
                required
                value={chiefComplaint}
                onChange={(e) => {
                  setChiefComplaint(e.target.value)
                  if (validationError) setValidationError(null)
                }}
                placeholder="Primary reason for visit"
                className={`${INPUT_BASE} resize-none`}
              />
              {validationError && (
                <p className="text-xs text-red-500 dark:text-red-400 mt-1" role="alert">
                  {validationError}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="narrative" className={LABEL}>
                Narrative / Additional Notes
              </label>
              <textarea
                id="narrative"
                rows={2}
                value={narrative}
                onChange={(e) => setNarrative(e.target.value)}
                placeholder="Additional observations"
                className={`${INPUT_BASE} resize-none`}
              />
            </div>
          </div>
        </div>

        {/* Section 3 — Vital Signs */}
        <div className={CARD}>
          <h2 className={SECTION_HEADER}>Vital Signs</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {/* Blood Pressure */}
            <div className="col-span-2 sm:col-span-1">
              <label className={LABEL}>Blood Pressure</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={0}
                  max={300}
                  value={bpSys}
                  onChange={(e) => setBpSys(e.target.value)}
                  placeholder="Systolic"
                  aria-label="BP Systolic"
                  className={INPUT_BASE}
                />
                <span className="text-[var(--foreground-muted)] font-bold shrink-0">/</span>
                <input
                  type="number"
                  min={0}
                  max={200}
                  value={bpDia}
                  onChange={(e) => setBpDia(e.target.value)}
                  placeholder="Diastolic"
                  aria-label="BP Diastolic"
                  className={INPUT_BASE}
                />
              </div>
            </div>

            <div>
              <label htmlFor="heart_rate" className={LABEL}>Heart Rate</label>
              <input
                id="heart_rate"
                type="number"
                min={0}
                max={300}
                value={heartRate}
                onChange={(e) => setHeartRate(e.target.value)}
                placeholder="bpm"
                className={INPUT_BASE}
              />
            </div>

            <div>
              <label htmlFor="resp_rate" className={LABEL}>Respiratory Rate</label>
              <input
                id="resp_rate"
                type="number"
                min={0}
                max={100}
                value={respRate}
                onChange={(e) => setRespRate(e.target.value)}
                placeholder="breaths/min"
                className={INPUT_BASE}
              />
            </div>

            <div>
              <label htmlFor="temperature" className={LABEL}>Temperature</label>
              <input
                id="temperature"
                type="number"
                min={90}
                max={115}
                step={0.1}
                value={temp}
                onChange={(e) => setTemp(e.target.value)}
                placeholder="°F"
                className={INPUT_BASE}
              />
            </div>

            <div>
              <label htmlFor="o2_sat" className={LABEL}>O₂ Saturation</label>
              <input
                id="o2_sat"
                type="number"
                min={0}
                max={100}
                value={o2sat}
                onChange={(e) => setO2sat(e.target.value)}
                placeholder="%"
                className={INPUT_BASE}
              />
            </div>

            {/* Pain Scale — spans full row */}
            <div className="col-span-2 sm:col-span-3">
              <label htmlFor="pain_scale" className={LABEL}>
                Pain Scale{' '}
                <span className="font-bold text-[var(--foreground)]">{pain}/10</span>
              </label>
              <input
                id="pain_scale"
                type="range"
                min={0}
                max={10}
                step={1}
                value={pain}
                onChange={(e) => setPain(Number(e.target.value))}
                className="w-full h-2 rounded-full appearance-none bg-[var(--border)] accent-emerald-500 cursor-pointer"
              />
              <div className="flex justify-between text-xs text-[var(--foreground-muted)] mt-1">
                <span>0 — No pain</span>
                <span>10 — Worst</span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 4 — Mental Status */}
        <div className={CARD}>
          <h2 className={SECTION_HEADER}>Mental Status</h2>
          <div className="grid grid-cols-2 gap-y-2 gap-x-4">
            {MENTAL_STATUS_OPTIONS.map((opt) => (
              <label key={opt.key} className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={!!mentalStatus[opt.key]}
                  onChange={(e) =>
                    setMentalStatus((prev) => ({ ...prev, [opt.key]: e.target.checked }))
                  }
                  className="w-4 h-4 rounded border-[var(--border)] accent-emerald-500"
                />
                <span className="text-sm text-[var(--foreground)]">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Section 5 — Past Medical History */}
        <div className={CARD}>
          <h2 className={SECTION_HEADER}>Past Medical History</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-y-2 gap-x-4">
            {PMH_OPTIONS.map((opt) => (
              <label key={opt.key} className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={!!pmh[opt.key]}
                  onChange={(e) =>
                    setPmh((prev) => ({ ...prev, [opt.key]: e.target.checked }))
                  }
                  className="w-4 h-4 rounded border-[var(--border)] accent-emerald-500"
                />
                <span className="text-sm text-[var(--foreground)]">{opt.label}</span>
              </label>
            ))}
            {/* Other */}
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={pmhOther}
                onChange={(e) => {
                  setPmhOther(e.target.checked)
                  if (!e.target.checked) setPmhOtherText('')
                }}
                className="w-4 h-4 rounded border-[var(--border)] accent-emerald-500"
              />
              <span className="text-sm text-[var(--foreground)]">Other</span>
            </label>
          </div>
          {pmhOther && (
            <div className="mt-3">
              <input
                type="text"
                value={pmhOtherText}
                onChange={(e) => setPmhOtherText(e.target.value)}
                placeholder="Specify other condition"
                className={INPUT_BASE}
                autoFocus
              />
            </div>
          )}
        </div>

        {/* Section 6 — Allergies & Medications */}
        <div className={CARD}>
          <h2 className={SECTION_HEADER}>Allergies &amp; Medications</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <div className="flex items-center gap-2.5 mb-2 cursor-pointer select-none">
                <input
                  id="no_known_allergies"
                  type="checkbox"
                  checked={noKnownAllergies}
                  onChange={(e) => {
                    setNoKnownAllergies(e.target.checked)
                    if (e.target.checked) setAllergies('')
                  }}
                  className="w-4 h-4 rounded border-[var(--border)] accent-emerald-500"
                />
                <label
                  htmlFor="no_known_allergies"
                  className="text-sm font-medium text-[var(--foreground)] cursor-pointer"
                >
                  No Known Allergies
                </label>
              </div>
              <input
                type="text"
                value={allergies}
                onChange={(e) => setAllergies(e.target.value)}
                placeholder="List allergies (e.g. Penicillin, latex)"
                disabled={noKnownAllergies}
                className={`${INPUT_BASE} disabled:opacity-40 disabled:cursor-not-allowed`}
                aria-label="Allergies"
              />
            </div>

            <div>
              <label htmlFor="medications" className={LABEL}>
                Current Medications
              </label>
              <textarea
                id="medications"
                rows={2}
                value={medications}
                onChange={(e) => setMedications(e.target.value)}
                placeholder="List current medications and doses"
                className={`${INPUT_BASE} resize-none`}
              />
            </div>
          </div>
        </div>

        {/* Section 7 — Clinical Images */}
        <div className={CARD}>
          <h2 className={SECTION_HEADER}>Clinical Images</h2>
          <p className="text-xs text-[var(--foreground-muted)] mb-3">
            Optional — attach wound photos, rashes, ECG strips, or other visual findings.
          </p>
          <label className="flex flex-col items-center justify-center gap-2 w-full py-6 border-2 border-dashed border-[var(--border)] rounded-lg cursor-pointer hover:border-emerald-400 dark:hover:border-emerald-500 transition-colors bg-[var(--background)]">
            <ImagePlus size={22} className="text-[var(--foreground-muted)]" strokeWidth={1.5} />
            <span className="text-sm text-[var(--foreground-muted)]">
              Click to upload images
            </span>
            <span className="text-xs text-[var(--foreground-muted)] opacity-70">
              JPEG, PNG, HEIC — up to 10 MB each
            </span>
            <input
              type="file"
              accept="image/*"
              multiple
              className="sr-only"
              onChange={(e) => {
                const files = Array.from(e.target.files ?? [])
                setImages((prev) => {
                  const existing = new Set(prev.map((f) => f.name))
                  return [...prev, ...files.filter((f) => !existing.has(f.name))]
                })
                e.target.value = ''
              }}
            />
          </label>
          {images.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {images.map((file, i) => (
                <li key={`${file.name}-${i}`} className="flex items-center gap-2 text-sm text-[var(--foreground)]">
                  <ImagePlus size={14} className="text-emerald-500 shrink-0" />
                  <span className="flex-1 truncate">{file.name}</span>
                  <span className="text-xs text-[var(--foreground-muted)] shrink-0">
                    {(file.size / 1024).toFixed(0)} KB
                  </span>
                  <button
                    type="button"
                    onClick={() => setImages((prev) => prev.filter((_, idx) => idx !== i))}
                    className="text-[var(--foreground-muted)] hover:text-red-500 transition-colors"
                    aria-label={`Remove ${file.name}`}
                  >
                    <X size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Error banner */}
        {mutationError && (
          <div
            role="alert"
            className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm"
          >
            Failed to submit case. Please try again.
          </div>
        )}

        {/* Submit */}
        <div className="flex justify-end pb-6">
          <button
            type="submit"
            disabled={isPending}
            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
          >
            {isPending ? (
              <>
                <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                Submitting…
              </>
            ) : (
              'Submit Triage'
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
