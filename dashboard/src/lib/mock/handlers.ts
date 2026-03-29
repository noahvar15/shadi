// MSW request handlers for offline / test mock mode.
// Intercepts all API calls used by the dashboard until the real backend is live.
import { http, HttpResponse } from 'msw'
import type { DifferentialReport } from '@/types/report'

let caseCounter = 1000

const MOCK_CASES: Array<{ case_id: string; patient_id: string; status: 'queued' | 'running' | 'complete'; created_at: string }> = [
  {
    case_id: 'CASE-DEMO-001',
    patient_id: 'PT-DEMO-001',
    status: 'complete' as const,
    created_at: new Date(Date.now() - 3600_000).toISOString(),
  },
  {
    case_id: 'CASE-DEMO-002',
    patient_id: 'PT-DEMO-002',
    status: 'running' as const,
    created_at: new Date(Date.now() - 900_000).toISOString(),
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
  http.get('/api/cases', () => {
    return HttpResponse.json(MOCK_CASES)
  }),

  http.post('/api/cases', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    const caseId = `CASE-${Date.now()}-${caseCounter++}`
    MOCK_CASES.unshift({
      case_id: caseId,
      patient_id: String(body.patient_stub_id ?? 'STUB'),
      status: 'queued',
      created_at: new Date().toISOString(),
    })
    return HttpResponse.json(
      { case_id: caseId, status: 'queued', patient_id: body.patient_stub_id ?? 'STUB' },
      { status: 201 },
    )
  }),

  http.get('/api/reports/:caseId', ({ params }) => {
    return HttpResponse.json({ ...MOCK_REPORT, case_id: params.caseId })
  }),

  http.get('/api/reports/:caseId/status', ({ params }) => {
    return HttpResponse.json({ case_id: params.caseId, status: 'running' })
  }),
]
