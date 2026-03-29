/**
 * API integration tests — verify that the dashboard's Axios client sends the
 * correct payloads and correctly handles responses for every route that talks
 * to the backend.
 *
 * MSW's Node server (msw-server.ts) intercepts all HTTP traffic so these tests
 * run without a live backend or database.  The same handler logic is used by
 * the browser mock (NEXT_PUBLIC_MOCK_API=true), so passing tests here give
 * high confidence that the real backend calls will behave identically once
 * FastAPI + Postgres is running.
 */
import { describe, it, expect } from 'vitest'
import { http, HttpResponse } from 'msw'
import { api } from '@/lib/api'
import { server, mockCases } from './msw-server'

// ─── Nurse: triage intake submission ────────────────────────────────────────

describe('POST /api/cases/intake — nurse triage submission', () => {
  it('sends chief_complaint, patient_name, and patient_stub_id in the request body', async () => {
    let captured: Record<string, unknown> = {}

    // Intercept to spy on the exact payload sent by the client
    server.use(
      http.post('http://localhost/api/cases/intake', async ({ request }) => {
        captured = await request.json() as Record<string, unknown>
        return HttpResponse.json({ case_id: 'CASE-SPY-001', status: 'queued' }, { status: 201 })
      }),
    )

    const payload = {
      chief_complaint: 'Chief Complaint: Chest pain\nVitals: BP 145/90, HR 102',
      patient_name: 'Robert Walsh',
      patient_stub_id: 'PT-2026-042',
    }

    await api.post('/api/cases/intake', payload)

    expect(captured.chief_complaint).toBe(payload.chief_complaint)
    expect(captured.patient_name).toBe('Robert Walsh')
    expect(captured.patient_stub_id).toBe('PT-2026-042')
  })

  it('returns case_id and status "queued" on success', async () => {
    const { data, status } = await api.post('/api/cases/intake', {
      chief_complaint: 'Chief Complaint: Headache',
      patient_name: 'Jane Doe',
    })

    expect(status).toBe(201)
    expect(data).toHaveProperty('case_id')
    expect(data.status).toBe('queued')
    expect(typeof data.case_id).toBe('string')
  })

  it('appends the new case to the cases list after submission', async () => {
    const before = mockCases.length

    await api.post('/api/cases/intake', {
      chief_complaint: 'Chief Complaint: Shortness of breath',
      patient_name: 'Alice Kim',
      patient_stub_id: 'PT-NEW-001',
    })

    expect(mockCases.length).toBe(before + 1)
    const newest = mockCases[0]
    expect(newest.patient_name).toBe('Alice Kim')
    expect(newest.patient_id).toBe('PT-NEW-001')
    expect(newest.status).toBe('queued')
    expect(newest.chief_complaint).toContain('Shortness of breath')
  })

  it('returns 422 when chief_complaint is missing', async () => {
    await expect(
      api.post('/api/cases/intake', { patient_name: 'No Complaint' }),
    ).rejects.toMatchObject({ response: { status: 422 } })
  })

  it('submitted case immediately appears in GET /api/cases response', async () => {
    const { data: queued } = await api.post<{ case_id: string }>('/api/cases/intake', {
      chief_complaint: 'Chief Complaint: Abdominal pain',
      patient_name: 'Tom Nguyen',
    })

    const { data: cases } = await api.get<Array<{ case_id: string }>>('/api/cases')
    const ids = cases.map((c) => c.case_id)
    expect(ids).toContain(queued.case_id)
  })
})

// ─── Doctor: active cases list ───────────────────────────────────────────────

describe('GET /api/cases — doctor active cases list', () => {
  it('returns an array of cases', async () => {
    const { data, status } = await api.get('/api/cases')

    expect(status).toBe(200)
    expect(Array.isArray(data)).toBe(true)
    expect(data.length).toBeGreaterThan(0)
  })

  it('each case has required fields: case_id, patient_id, status, created_at', async () => {
    const { data } = await api.get<Array<Record<string, unknown>>>('/api/cases')

    for (const c of data) {
      expect(c).toHaveProperty('case_id')
      expect(c).toHaveProperty('patient_id')
      expect(c).toHaveProperty('status')
      expect(c).toHaveProperty('created_at')
    }
  })

  it('includes patient_name and chief_complaint fields', async () => {
    const { data } = await api.get<Array<Record<string, unknown>>>('/api/cases')
    const complete = data.find((c) => c.status === 'complete')

    expect(complete).toBeDefined()
    expect(complete).toHaveProperty('patient_name')
    expect(complete).toHaveProperty('chief_complaint')
  })

  it('status values are valid pipeline states', async () => {
    const VALID = new Set(['queued', 'processing', 'complete', 'failed', 'pending_enqueue', 'enqueue_failed'])
    const { data } = await api.get<Array<{ status: string }>>('/api/cases')

    for (const c of data) {
      expect(VALID.has(c.status), `unexpected status "${c.status}"`).toBe(true)
    }
  })

  it('reflects newly submitted cases immediately', async () => {
    const initialCount = (await api.get<unknown[]>('/api/cases')).data.length

    await api.post('/api/cases/intake', {
      chief_complaint: 'Chief Complaint: Dizziness',
      patient_name: 'Sara Park',
    })

    const { data: updated } = await api.get<unknown[]>('/api/cases')
    expect(updated.length).toBe(initialCount + 1)
  })
})

// ─── Triage document: single case fetch ──────────────────────────────────────

describe('GET /api/cases/:id — triage document fetch', () => {
  it('returns full case detail for a known case_id', async () => {
    const { data, status } = await api.get('/api/cases/CASE-DEMO-001')

    expect(status).toBe(200)
    expect(data.case_id).toBe('CASE-DEMO-001')
    expect(data.patient_name).toBe('Maria Gonzalez')
    expect(data.patient_id).toBe('PT-DEMO-001')
  })

  it('chief_complaint contains structured triage sections', async () => {
    const { data } = await api.get<{ chief_complaint: string }>('/api/cases/CASE-DEMO-001')

    expect(data.chief_complaint).toMatch(/Chief Complaint:/i)
    expect(data.chief_complaint).toMatch(/Vitals:/i)
  })

  it('returns 404 for an unknown case_id', async () => {
    await expect(
      api.get('/api/cases/CASE-DOES-NOT-EXIST'),
    ).rejects.toMatchObject({ response: { status: 404 } })
  })

  it('newly submitted case is fetchable by its returned case_id', async () => {
    const { data: intake } = await api.post<{ case_id: string }>('/api/cases/intake', {
      chief_complaint: 'Chief Complaint: Severe back pain\nVitals: BP 130/80',
      patient_name: 'Michael Torres',
      patient_stub_id: 'PT-2026-099',
    })

    const { data: detail } = await api.get(`/api/cases/${intake.case_id}`)

    expect(detail.case_id).toBe(intake.case_id)
    expect(detail.patient_name).toBe('Michael Torres')
    expect(detail.chief_complaint).toContain('Severe back pain')
  })
})

// ─── Doctor feedback: thumbs up / down ───────────────────────────────────────

describe('POST /api/cases/:id/feedback — doctor triage feedback', () => {
  it('accepts a thumbs-up vote and returns { ok: true }', async () => {
    const { data, status } = await api.post('/api/cases/CASE-DEMO-001/feedback', {
      vote: 'up',
    })

    expect(status).toBe(200)
    expect(data.ok).toBe(true)
  })

  it('accepts a thumbs-down vote and returns { ok: true }', async () => {
    const { data } = await api.post('/api/cases/CASE-DEMO-001/feedback', {
      vote: 'down',
      note: 'Vitals seem inconsistent with the narrative',
    })

    expect(data.ok).toBe(true)
  })

  it('sends vote and optional note in the request body', async () => {
    let captured: Record<string, unknown> = {}

    server.use(
      http.post('http://localhost/api/cases/:caseId/feedback', async ({ request }) => {
        captured = await request.json() as Record<string, unknown>
        return HttpResponse.json({ ok: true })
      }),
    )

    await api.post('/api/cases/CASE-DEMO-001/feedback', {
      vote: 'down',
      note: 'Missing mental status',
    })

    expect(captured.vote).toBe('down')
    expect(captured.note).toBe('Missing mental status')
  })

  it('returns 404 for feedback on a non-existent case', async () => {
    await expect(
      api.post('/api/cases/CASE-GHOST/feedback', { vote: 'up' }),
    ).rejects.toMatchObject({ response: { status: 404 } })
  })

  it('accepts null to clear a previous vote', async () => {
    const { data } = await api.post('/api/cases/CASE-DEMO-001/feedback', { vote: null })
    expect(data.ok).toBe(true)
  })

  it('returns 422 for a completely invalid vote value', async () => {
    await expect(
      api.post('/api/cases/CASE-DEMO-001/feedback', { vote: 'maybe' }),
    ).rejects.toMatchObject({ response: { status: 422 } })
  })
})

// ─── Reports ─────────────────────────────────────────────────────────────────

describe('GET /api/reports/:id — diagnostic report', () => {
  it('returns a complete report with top_diagnoses for a completed case', async () => {
    const { data } = await api.get('/api/reports/CASE-DEMO-001')
    expect(data.status).toBe('complete')
    expect(data.case_id).toBe('CASE-DEMO-001')
    expect(Array.isArray(data.top_diagnoses)).toBe(true)
    expect(data.top_diagnoses.length).toBeGreaterThan(0)
    expect(data.top_diagnoses[0]).toHaveProperty('display')
    expect(data.top_diagnoses[0]).toHaveProperty('confidence')
    expect(typeof data.consensus_level).toBe('number')
    expect(Array.isArray(data.divergent_agents)).toBe(true)
    expect(Array.isArray(data.vetoed_recommendations)).toBe(true)
  })

  it('returns in-progress status with empty diagnoses for a processing case', async () => {
    const { data } = await api.get('/api/reports/CASE-DEMO-002')
    expect(data.status).toBe('processing')
    expect(data.top_diagnoses).toEqual([])
    expect(data.pipeline_step).toBeTruthy()
  })

  it('returns a complete fallback for an unknown case id', async () => {
    const { data } = await api.get('/api/reports/CASE-UNKNOWN-999')
    expect(data.status).toBe('complete')
    expect(data.case_id).toBe('CASE-UNKNOWN-999')
  })
})

describe('GET /api/reports/:id/status — report status', () => {
  it('returns status for a completed case', async () => {
    const { data } = await api.get('/api/reports/CASE-DEMO-001/status')
    expect(data.status).toBe('complete')
  })

  it('returns processing status for an in-progress case', async () => {
    const { data } = await api.get('/api/reports/CASE-DEMO-002/status')
    expect(data.status).toBe('processing')
  })
})
