import { http, HttpResponse } from 'msw'
import type { DifferentialReport } from '@/types/report'

let caseCounter = 1000

const PIPELINE_STEPS = ['specialists', 'evidence', 'debate', 'synthesis', 'safety'] as const
const PIPELINE_DURATION_MS = 12_000

interface PipelineState {
  startedAt: number
  completedAt?: number
}
const pipelineStates = new Map<string, PipelineState>()

function getPipelineStatus(caseId: string): { status: string; pipeline_step: string | null; completed_at: string | null } {
  const state = pipelineStates.get(caseId)
  if (!state) return { status: 'complete', pipeline_step: null, completed_at: new Date(Date.now() - 1800_000).toISOString() }
  if (state.completedAt) return { status: 'complete', pipeline_step: null, completed_at: new Date(state.completedAt).toISOString() }
  const elapsed = Date.now() - state.startedAt
  if (elapsed >= PIPELINE_DURATION_MS) {
    state.completedAt = Date.now()
    return { status: 'complete', pipeline_step: null, completed_at: new Date(state.completedAt).toISOString() }
  }
  const stepIdx = Math.min(Math.floor((elapsed / PIPELINE_DURATION_MS) * PIPELINE_STEPS.length), PIPELINE_STEPS.length - 1)
  return { status: 'processing', pipeline_step: PIPELINE_STEPS[stepIdx], completed_at: null }
}

const MOCK_PATIENTS = [
  { patient_id: 'PT-DEMO-001', patient_name: 'Maria Gonzalez', dob: '1978-04-15' },
  { patient_id: 'PT-DEMO-002', patient_name: 'James Okafor', dob: '1955-09-22' },
  { patient_id: 'PT-DEMO-003', patient_name: 'Helen Park', dob: '1990-03-07' },
  { patient_id: 'PT-DEMO-004', patient_name: 'Robert Chen', dob: '1963-11-30' },
  { patient_id: 'PT-DEMO-005', patient_name: 'Angela Torres', dob: '2001-07-19' },
]

interface MockCase {
  case_id: string
  patient_id: string
  patient_name: string
  status: 'queued' | 'processing' | 'complete'
  created_at: string
  chief_complaint: string
}

const MOCK_CASES: MockCase[] = [
  {
    case_id: 'CASE-DEMO-001',
    patient_id: 'PT-DEMO-001',
    patient_name: 'Maria Gonzalez',
    status: 'complete',
    created_at: new Date(Date.now() - 3600_000).toISOString(),
    chief_complaint: [
      'Chief Complaint: Chest pain radiating to left arm',
      'Vitals: BP 145/92, HR 102, RR 18, Temp 98.6°F, O2 97%, Pain 8/10',
      'Mental Status: Alert/Oriented',
      'PMH: Hypertension (HTN), Heart Disease',
      'Allergies: Penicillin',
      'Medications: Lisinopril 10mg, Aspirin 81mg',
      'Narrative: Onset 2 hours ago, radiating to left arm and jaw. Diaphoretic.',
    ].join('\n'),
  },
  {
    case_id: 'CASE-DEMO-002',
    patient_id: 'PT-DEMO-002',
    patient_name: 'James Okafor',
    status: 'processing',
    created_at: new Date(Date.now() - 900_000).toISOString(),
    chief_complaint: [
      'Chief Complaint: Sudden severe headache',
      'Vitals: BP 188/110, HR 78, RR 16, Temp 98.2°F, O2 99%, Pain 10/10',
      'Mental Status: Alert/Oriented, Aphasic',
      'PMH: Hypertension (HTN), Stroke/CVA',
      'Allergies: No Known Allergies',
      'Medications: Metoprolol 25mg',
      'Narrative: Patient describes "worst headache of my life". Sudden onset while at rest.',
    ].join('\n'),
  },
]

const MOCK_REPORT: DifferentialReport = {
  case_id: 'CASE-DEMO-001',
  status: 'complete',
  consensus_level: 0.9,
  divergent_agents: [],
  completed_at: new Date(Date.now() - 1800_000).toISOString(),
  top_diagnoses: [
    {
      rank: 1,
      display: 'Acute Myocardial Infarction',
      snomed_code: '57054005',
      confidence: 0.87,
      next_steps: ['Urgent ECG', 'Troponin levels', 'Cardiology consult'],
      supporting_evidence: [
        {
          source: 'PubMed:12345678',
          excerpt: 'Chest pain with radiation to the left arm is a classic presentation of AMI.',
          relevance_score: 0.92,
        },
      ],
      flags: [],
    },
    {
      rank: 2,
      display: 'Unstable Angina',
      snomed_code: '4557003',
      confidence: 0.61,
      next_steps: ['Serial ECGs', 'Biomarker monitoring'],
      supporting_evidence: [],
      flags: [],
    },
  ],
  vetoed_recommendations: [],
}

export const handlers = [
  // ── Patient search ───────────────────────────────────────────────────────────
  http.get('/api/patients/search', ({ request }) => {
    const query = new URL(request.url).searchParams.get('name') ?? ''
    const lower = query.toLowerCase()
    const results = MOCK_PATIENTS.filter((p) =>
      p.patient_name.toLowerCase().includes(lower)
    )
    return HttpResponse.json(results)
  }),

  // ── Cases list ──────────────────────────────────────────────────────────────
  http.get('/api/cases', () => {
    const cases = MOCK_CASES.map((c) => {
      const ps = getPipelineStatus(c.case_id)
      return { ...c, status: ps.status === 'complete' ? 'complete' : c.status === 'complete' ? 'complete' : ps.status }
    })
    return HttpResponse.json(cases)
  }),

  // ── Individual case (for triage doc) ────────────────────────────────────────
  http.get('/api/cases/:caseId', ({ params }) => {
    const found = MOCK_CASES.find((c) => c.case_id === params.caseId)
    if (!found) {
      return HttpResponse.json({ detail: 'Case not found' }, { status: 404 })
    }
    return HttpResponse.json(found)
  }),

  // ── Nurse triage intake ──────────────────────────────────────────────────────
  http.post('/api/cases/intake', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    const caseId = `CASE-${Date.now()}-${caseCounter++}`
    pipelineStates.set(caseId, { startedAt: Date.now() })
    MOCK_CASES.unshift({
      case_id: caseId,
      patient_id: String(body.patient_stub_id ?? 'STUB'),
      patient_name: String(body.patient_name ?? 'Unknown Patient'),
      status: 'processing',
      created_at: new Date().toISOString(),
      chief_complaint: String(body.chief_complaint ?? ''),
    })
    return HttpResponse.json(
      { case_id: caseId, status: 'queued' },
      { status: 201 },
    )
  }),

  // ── Legacy FHIR bundle intake (kept for backward compatibility) ─────────────
  http.post('/api/cases', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    const caseId = `CASE-${Date.now()}-${caseCounter++}`
    MOCK_CASES.unshift({
      case_id: caseId,
      patient_id: String(body.patient_stub_id ?? 'STUB'),
      patient_name: String(body.patient_name ?? 'Unknown Patient'),
      status: 'queued',
      created_at: new Date().toISOString(),
      chief_complaint: String(body.chief_complaint ?? ''),
    })
    return HttpResponse.json(
      { case_id: caseId, status: 'queued' },
      { status: 201 },
    )
  }),

  // ── Doctor feedback (thumbs up / down) ─────────────────────────────────────
  http.post('/api/cases/:caseId/feedback', () => {
    return HttpResponse.json({ ok: true })
  }),

  // ── Reports ─────────────────────────────────────────────────────────────────
  http.get('/api/reports/:caseId', ({ params }) => {
    const caseId = String(params.caseId)
    const ps = getPipelineStatus(caseId)

    if (ps.status !== 'complete') {
      return HttpResponse.json({
        case_id: caseId,
        status: ps.status,
        pipeline_step: ps.pipeline_step,
        top_diagnoses: [],
        consensus_level: 0,
        divergent_agents: [],
        vetoed_recommendations: [],
        completed_at: null,
        error_message: null,
      })
    }

    return HttpResponse.json({
      ...MOCK_REPORT,
      case_id: caseId,
      completed_at: ps.completed_at,
      pipeline_step: null,
    })
  }),

  http.get('/api/reports/:caseId/status', ({ params }) => {
    const ps = getPipelineStatus(String(params.caseId))
    return HttpResponse.json({ case_id: params.caseId, status: ps.status })
  }),
]
