// MSW request handlers for offline / test mock mode.
// Intercepts POST /cases and GET /reports/{id} during local development
// until the real backend endpoints are live.
import { http, HttpResponse } from 'msw'

let caseCounter = 1000

export const handlers = [
  http.post('/api/cases', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    const caseId = `CASE-${Date.now()}-${caseCounter++}`
    return HttpResponse.json(
      { case_id: caseId, status: 'queued', patient_id: body.patient_id ?? 'STUB' },
      { status: 201 },
    )
  }),

  http.get('/api/reports/:caseId/status', ({ params }) => {
    return HttpResponse.json({ case_id: params.caseId, status: 'running' })
  }),
]
