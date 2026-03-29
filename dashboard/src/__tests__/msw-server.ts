/**
 * MSW Node server for unit / integration tests.
 *
 * Uses the same handler logic as the browser mock (src/lib/mock/handlers.ts)
 * but registers routes against the test base URL (http://localhost) that the
 * Axios client resolves to when NEXT_PUBLIC_API_URL=http://localhost.
 */
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

export interface MockCase {
  case_id: string
  patient_id: string
  patient_name: string
  status: 'queued' | 'processing' | 'complete' | 'failed'
  created_at: string
  chief_complaint: string
}

// Seed cases — reset to this after each test via server.resetHandlers()
const SEED_CASES: MockCase[] = [
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
    ].join('\n'),
  },
  {
    case_id: 'CASE-DEMO-002',
    patient_id: 'PT-DEMO-002',
    patient_name: 'James Okafor',
    status: 'processing',
    created_at: new Date(Date.now() - 900_000).toISOString(),
    chief_complaint: 'Chief Complaint: Sudden severe headache\nVitals: BP 188/110, HR 78',
  },
]

// Mutable list that tests can inspect / mutate
export let mockCases: MockCase[] = [...SEED_CASES]

// Expose a helper so setup.ts can reset between tests
export function resetMockCases() {
  mockCases = [...SEED_CASES]
}

let caseCounter = 9000

export const server = setupServer(
  // GET /api/cases — list all cases
  http.get('http://localhost/api/cases', () => {
    return HttpResponse.json(mockCases)
  }),

  // GET /api/cases/:id — single case
  http.get('http://localhost/api/cases/:caseId', ({ params }) => {
    const found = mockCases.find((c) => c.case_id === params.caseId)
    if (!found) {
      return HttpResponse.json({ detail: 'Case not found' }, { status: 404 })
    }
    return HttpResponse.json(found)
  }),

  // POST /api/cases/intake — nurse triage submission
  http.post('http://localhost/api/cases/intake', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>

    // Require chief_complaint — mirrors backend validation
    if (!body.chief_complaint) {
      return HttpResponse.json(
        { detail: 'chief_complaint is required' },
        { status: 422 },
      )
    }

    const caseId = `CASE-TEST-${caseCounter++}`
    const newCase: MockCase = {
      case_id: caseId,
      patient_id: String(body.patient_stub_id ?? 'stub'),
      patient_name: String(body.patient_name ?? 'Unknown Patient'),
      status: 'queued',
      created_at: new Date().toISOString(),
      chief_complaint: String(body.chief_complaint),
    }
    mockCases.unshift(newCase)

    return HttpResponse.json({ case_id: caseId, status: 'queued' }, { status: 201 })
  }),

  // POST /api/cases/:id/feedback — doctor thumbs up / down
  http.post('http://localhost/api/cases/:caseId/feedback', async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>
    const found = mockCases.find((c) => c.case_id === params.caseId)
    if (!found) {
      return HttpResponse.json({ detail: 'Case not found' }, { status: 404 })
    }
    if (body.vote !== 'up' && body.vote !== 'down' && body.vote !== null) {
      return HttpResponse.json({ detail: 'vote must be "up", "down", or null' }, { status: 422 })
    }
    return HttpResponse.json({ ok: true })
  }),

  // GET /api/reports/:id — full report or in-progress
  http.get('http://localhost/api/reports/:caseId', ({ params }) => {
    const caseId = String(params.caseId)
    const found = mockCases.find((c) => c.case_id === caseId)

    if (found && found.status !== 'complete') {
      return HttpResponse.json({
        case_id: caseId,
        status: found.status,
        pipeline_step: 'specialists',
        top_diagnoses: [],
        consensus_level: 0,
        divergent_agents: [],
        vetoed_recommendations: [],
        completed_at: null,
        error_message: null,
      })
    }

    return HttpResponse.json({
      case_id: caseId,
      status: 'complete',
      pipeline_step: null,
      top_diagnoses: [
        {
          rank: 1,
          display: 'Acute Myocardial Infarction',
          snomed_code: '57054005',
          confidence: 0.87,
          next_steps: ['Urgent ECG', 'Troponin levels'],
          supporting_evidence: [],
          flags: [],
        },
      ],
      consensus_level: 0.9,
      divergent_agents: [],
      vetoed_recommendations: [],
      completed_at: new Date().toISOString(),
      error_message: null,
    })
  }),

  // GET /api/reports/:id/status
  http.get('http://localhost/api/reports/:caseId/status', ({ params }) => {
    const caseId = String(params.caseId)
    const found = mockCases.find((c) => c.case_id === caseId)
    const status = found ? found.status : 'complete'
    return HttpResponse.json({ case_id: caseId, status })
  }),
)
