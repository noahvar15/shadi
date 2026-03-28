# Cross-Track Dependencies

**Last updated:** 2026-03-28

This document maps every dependency between the four parallel development tracks so contributors know what they are waiting on, what they are blocking, and how to stay unblocked while those dependencies resolve.

---

## Track owners

| Track | Owner | Epic issue | Core directory |
|---|---|---|---|
| FHIR / EHR | Noah Vargas (`noahvar15`) | #25 | `fhir/` |
| Backend platform | Emmanuel Giron (`Manny-Giron`) | #30 | `api/` |
| Agents | Joshua Pereira (`Josh7511`) | #35 | `agents/`, `a2a/` |
| Dashboard | Ericsen Semedo (`EricsenSemedo`) | #40 | `dashboard/` |

---

## Dependency map

```
Noah (FHIR)         #28 ──────────────────────────────► #26 ──► #27 ──► #29
                     │
                     │  bundle_to_case() output
                     ▼
Emmanuel (API)      #31 ──► #32 ──────────────────────────────► #33 ──► #34
                             │                  ▲
                             │  POST /cases      │  Orchestrator.run()
                             │  response shape   │
                             │                  │
Joshua (Agents)     #36 ──► #37 ──► #38 ──────► #39
                     │
                     │  (no API deps — agents call Ollama/vLLM directly)
                     │
Ericsen (Dashboard) #41 ──► #42 ──────────────► #43 ──► #44
                             │                   │
                             │  mock until #32    │  mock until #33
                             │  is live           │  is live
```

---

## Dependency details

### DEP-1: Noah #28 → Emmanuel #32

| | |
|---|---|
| **Produces** | `FHIRNormalizer.bundle_to_case(bundle_json) -> CaseObject` in `fhir/normalizer.py` |
| **Consumed by** | `POST /cases` in `api/routes/cases.py` — calls the normalizer to convert the incoming FHIR bundle into a `CaseObject` before DB insert |
| **Blocked task** | #32 full implementation |
| **How to stay unblocked** | Emmanuel: implement the route with a stub normalizer call: `case = CaseObject(patient_id="stub", ...)`. Wire in the real normalizer once #28 is merged. |

---

### DEP-2: Joshua #39 → Emmanuel #33

| | |
|---|---|
| **Produces** | A fully wired `Orchestrator.run(case) -> DifferentialReport` in `agents/orchestrator/orchestrator.py` |
| **Consumed by** | `GET /reports/{case_id}` in `api/routes/reports.py` — the arq job (`tasks/pipeline.py`) calls `Orchestrator().run(case)` and persists the result |
| **Blocked task** | #33 returning real report data |
| **How to stay unblocked** | Emmanuel: implement the arq task stub that returns a hardcoded `DifferentialReport` fixture. The route shape, DB persistence, and polling logic are all independent of Joshua's work. |

---

### DEP-3: Emmanuel #32 → Ericsen #42

| | |
|---|---|
| **Produces** | `POST /cases` returning `{ "case_id": str, "status": "queued" }` |
| **Consumed by** | Case intake form submission in `app/cases/new/page.tsx` |
| **Blocked task** | #42 live API integration |
| **How to stay unblocked** | Ericsen: build the entire form and submission flow against an [MSW](https://mswjs.io/) mock handler that returns a hardcoded `case_id`. Swap the mock for the real URL when #32 is deployed. |

---

### DEP-4: Emmanuel #33 → Ericsen #43 and #44

| | |
|---|---|
| **Produces** | `GET /reports/{case_id}` returning `DifferentialReport` JSON, and `GET /reports/{case_id}/status` for polling |
| **Consumed by** | Report view (`app/cases/[id]/page.tsx`) and live update hook |
| **Blocked tasks** | #43 live report data, #44 polling/SSE wiring |
| **How to stay unblocked** | Ericsen: build all components against `tests/fixtures/sample_report.json`. Every component — `DifferentialList`, `CitationPanel`, `DebateSummary`, `SafetyBanner` — can be driven by a static fixture. Replace with the real `useQuery` call once #33 is live. |

---

## What is NOT a dependency (common misconception)

| Assumption | Reality |
|---|---|
| "I need the DB running to implement my route" | Route shape, Pydantic models, and response schemas are pure Python — no DB needed to write and test them |
| "I need vLLM/Ollama running to implement an agent" | `BaseAgent.reason()` just makes an HTTP call. Point `inference_url` at a local mock server (e.g. `python -m http.server`) or use `unittest.mock.AsyncMock` in tests |
| "I need the backend running to build dashboard components" | All dashboard components can be built against static JSON fixtures. MSW intercepts `axios` calls in the browser — no backend required |
| "I need Noah's normalizer to start the cases route" | `router = APIRouter()` (two lines) is all that is needed to fix the startup import crash. Full normalizer integration is a separate step |

---

## Integration checkpoints

These are the moments when two tracks need to sync:

| Checkpoint | When | Who syncs |
|---|---|---|
| **Normalizer API contract** | Before #28 is merged | Noah + Emmanuel agree on the exact `CaseObject` fields that `bundle_to_case` guarantees to populate |
| **Orchestrator job signature** | Before #39 is merged | Joshua + Emmanuel agree on the arq task signature: `run_diagnostic_pipeline(ctx, case_id: str)` and what the persisted `DifferentialReport` JSON looks like |
| **API response shapes** | Before #32/#33 are merged | Emmanuel + Ericsen agree on exact JSON field names so mock fixtures match the real responses |
| **Inference URL config** | Before #36 is merged | Joshua + Emmanuel confirm `OLLAMA_BASE_URL` and `VLLM_BASE_URL` env var names match `api/config.py` `Settings` model |

---

## Start-of-sprint checklist (day one, no waiting)

Each track owner can begin these tasks immediately with zero cross-track dependencies:

- **Noah**: implement `FHIRNormalizer.bundle_to_case()` (#28) — pure Python, no services required
- **Emmanuel**: add `router = APIRouter()` to `api/routes/cases.py` and `api/routes/reports.py` to fix the startup import crash, then wire the lifespan (#31)
- **Joshua**: implement the six agent classes (#36) — subclass `BaseAgent`, write prompts, set `inference_url` and `model` class attributes
- **Ericsen**: run `bunx create-next-app` and scaffold the app (#41) — zero dependencies

---

## Shared contracts (do not change without notifying all tracks)

These interfaces are depended on by multiple tracks. Any changes must be communicated before merging.

| Contract | Defined in | Used by |
|---|---|---|
| `CaseObject` schema | `agents/schemas.py` | All tracks |
| `DifferentialReport` schema | `agents/schemas.py` | Joshua (produces), Emmanuel (persists), Ericsen (renders) |
| `SpecialistResult` schema | `agents/schemas.py` | Joshua (produces), orchestrator (consumes) |
| `VetoDecision` / `SafetyResult` | `agents/schemas.py` | Joshua (produces), orchestrator + Ericsen (consumes) |
| `OLLAMA_BASE_URL` / `VLLM_BASE_URL` env vars | `.env.example`, `api/config.py` | Emmanuel (defines), Joshua (uses) |
| `INTAKE_QUEUE` arq queue name | `.env.example` | Emmanuel (enqueues), Joshua (arq worker consumes) |
| `POST /cases` response shape | `api/routes/cases.py` | Emmanuel (defines), Ericsen (consumes) |
| `GET /reports/{id}` response shape | `api/routes/reports.py` | Emmanuel (defines), Ericsen (consumes) |
