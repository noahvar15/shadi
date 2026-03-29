import { ClipboardList, User, Calendar, Stethoscope } from 'lucide-react'

interface Props {
  chiefComplaint: string
  patientId: string
  createdAt: string
  patientName?: string
}

interface DocSection {
  label: string
  value: string
}

function parseTriageNote(text: string): DocSection[] {
  const sections: DocSection[] = []
  for (const line of text.split('\n')) {
    const colonIdx = line.indexOf(':')
    if (colonIdx === -1) continue
    const label = line.slice(0, colonIdx).trim()
    const value = line.slice(colonIdx + 1).trim()
    if (label && value) sections.push({ label, value })
  }
  return sections
}

// Sections that should render values in monospace (numbers, codes)
const MONO_SECTIONS = new Set(['Vitals', 'Pain Scale'])

export function TriageDoc({ chiefComplaint, patientId, createdAt, patientName }: Props) {
  const sections = parseTriageNote(chiefComplaint)

  return (
    <article className="max-w-2xl mx-auto">
      {/* Document header */}
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="px-6 py-5 border-b border-[var(--border)] bg-emerald-50 dark:bg-emerald-900/10">
          <div className="flex items-start gap-3">
            <ClipboardList
              size={22}
              className="text-emerald-600 dark:text-emerald-400 mt-0.5 shrink-0"
              strokeWidth={1.75}
            />
            <div>
              <h1 className="text-lg font-bold text-[var(--foreground)]">
                Triage Intake Note
              </h1>
              <p className="text-xs text-[var(--foreground-muted)] mt-0.5">
                Emergency Department — Shadi Clinical Reasoning System
              </p>
            </div>
          </div>
        </div>

        {/* Patient metadata bar */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 px-6 py-4 border-b border-[var(--border)] text-xs">
          <div className="flex items-center gap-2 text-[var(--foreground-muted)]">
            <User size={13} strokeWidth={1.75} className="shrink-0" />
            <div>
              <p className="font-semibold text-[var(--foreground)]">
                {patientName ?? '—'}
              </p>
              <p className="font-mono">{patientId}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-[var(--foreground-muted)]">
            <Calendar size={13} strokeWidth={1.75} className="shrink-0" />
            <div>
              <p className="font-semibold text-[var(--foreground)]">Admitted</p>
              <p>
                {new Date(createdAt).toLocaleString(undefined, {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-[var(--foreground-muted)]">
            <Stethoscope size={13} strokeWidth={1.75} className="shrink-0" />
            <div>
              <p className="font-semibold text-[var(--foreground)]">Source</p>
              <p>Nurse Triage Form</p>
            </div>
          </div>
        </div>

        {/* Triage sections */}
        {sections.length > 0 ? (
          <dl className="divide-y divide-[var(--border)]">
            {sections.map((s) => (
              <div
                key={s.label}
                className="grid grid-cols-[160px_1fr] gap-4 px-6 py-4 items-baseline"
              >
                <dt className="text-xs font-semibold uppercase tracking-wider text-[var(--foreground-muted)]">
                  {s.label}
                </dt>
                <dd
                  className={`text-sm text-[var(--foreground)] ${MONO_SECTIONS.has(s.label) ? 'font-mono' : ''}`}
                >
                  {s.value}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <div className="px-6 py-10 text-center text-sm text-[var(--foreground-muted)]">
            <p>No structured triage data available for this case.</p>
            {chiefComplaint && (
              <pre className="mt-4 text-left text-xs whitespace-pre-wrap font-mono bg-[var(--background)] border border-[var(--border)] rounded-lg p-4">
                {chiefComplaint}
              </pre>
            )}
          </div>
        )}

        {/* Footer stamp */}
        <div className="px-6 py-3 border-t border-[var(--border)] bg-[var(--background)] flex items-center justify-between text-[10px] text-[var(--foreground-muted)]">
          <span>SHADI · Triage Note · Read-only</span>
          <span className="font-mono">{patientId}</span>
        </div>
      </div>
    </article>
  )
}
