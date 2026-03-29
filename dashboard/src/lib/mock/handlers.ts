// MSW request handlers for offline / test mock mode.
// Intercepts all API calls used by the dashboard until the real backend is live.
import { http, HttpResponse } from 'msw'
import type { DifferentialReport } from '@/types/report'

let caseCounter = 1000

interface MockCase {
  case_id: string
  patient_id: string
  patient_name: string
  status: 'queued' | 'running' | 'complete'
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
    status: 'running',
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
  created_at: new Date(Date.now() - 3600_000).toISOString(),
  completed_at: new Date(Date.now() - 3000_000).toISOString(),
  consensus_level: 0.9,
  divergent_agents: [],
  top_diagnoses: [
    {
      diagnosis: 'Acute Myocardial Infarction',
      icd_code: 'I21.9',
      confidence: 0.87,
      reasoning_trace: [
        'Chest pain radiating to left arm with 2-hour onset',
        'Classic STEMI presentation pattern',
      ],
      next_steps: ['Urgent ECG', 'Troponin levels', 'Cardiology consult'],
      supporting_evidence: [
        {
          source: 'PubMed:12345678',
          excerpt: 'Chest pain with radiation to the left arm is a classic presentation of AMI.',
          relevance_score: 0.92,
        },
      ],
    },
    {
      diagnosis: 'Unstable Angina',
      icd_code: 'I20.0',
      confidence: 0.61,
      reasoning_trace: ['Chest pain pattern consistent with ischemic origin'],
      next_steps: ['Serial ECGs', 'Biomarker monitoring'],
      supporting_evidence: [],
    },
  ],
  vetoed_recommendations: [],
}

export const handlers = [
  // ── Cases list ──────────────────────────────────────────────────────────────
  http.get('/api/cases', () => {
    return HttpResponse.json(MOCK_CASES)
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
    return HttpResponse.json({ ...MOCK_REPORT, case_id: params.caseId })
  }),

  http.get('/api/reports/:caseId/status', ({ params }) => {
    return HttpResponse.json({ case_id: params.caseId, status: 'running' })
  }),
]
