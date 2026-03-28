# Shadi

**Multi-agent clinical diagnostic reasoning system for emergency medicine.**

> Temporary note for test PR validation. This line can be removed when the PR is deleted.

A patient case arrives from the EHR via FHIR R4. Five specialist agents — each running a domain-specific LoRA adapter on a shared 70B base model — reason independently over the case, debate via a structured A2A protocol, and produce a ranked differential diagnosis with confidence scores, evidence citations, and a safety veto layer. The attending physician receives this before walking into the room.

---

## Why This Exists

Diagnostic errors in emergency medicine are estimated to affect 12 million patients annually in the US. The window between triage and physician assessment is the highest-leverage moment to surface differential diagnoses that a single clinician might miss under time pressure. Shadi is designed to run in that window — locally, with no PHI leaving the machine.

---

## Architecture

```mermaid
flowchart TD
    EHR["EHR (Epic / Cerner)"]
    MCP["FHIR R4 MCP Server\n(encounter subscription)"]
    Intake["Intake Agent\n(SNOMED · LOINC · RxNorm)"]
    CaseObj["CaseObject"]

    Cardio["Cardiology Agent\n(LoRA adapter)"]
    Neuro["Neurology Agent\n(LoRA adapter)"]
    Pulm["Pulmonology Agent\n(LoRA adapter)"]
    Tox["Toxicology Agent\n(LoRA adapter)"]

    Evidence["Evidence Grounding Agent\n(PubMed + guidelines corpus)"]
    Debate["A2A Debate Round\n(ENDORSE · CHALLENGE · MODIFY)"]
    Orchestrator["Orchestrator\n(consensus + divergence tracking)"]
    Veto["Safety Veto Agent\n(meds · allergies · contraindications)"]
    Output["DiagnosticReport (FHIR)\n+ Physician Dashboard"]

    EHR --> MCP --> Intake --> CaseObj
    CaseObj --> Cardio & Neuro & Pulm & Tox
    Cardio & Neuro & Pulm & Tox --> Evidence
    Evidence --> Debate --> Orchestrator --> Veto --> Output
```

### Agent Pipeline

| Stage | Agent | Responsibility |
|---|---|---|
| 1 | **Intake** | Parse unstructured triage notes; extract SNOMED CT, LOINC, RxNorm codes; build `CaseObject` |
| 2 | **Specialists ×4** | Cardiology, neurology, pulmonology, toxicology reason concurrently; no cross-talk yet |
| 3 | **Evidence Grounding** | Each specialist's findings cross-referenced against local PubMed + clinical guidelines corpus; unsupported claims flagged |
| 4 | **A2A Debate** | Agents exchange structured `ENDORSE / CHALLENGE / MODIFY` messages; orchestrator tracks consensus and divergence |
| 5 | **Safety Veto** | Every recommended diagnostic step and treatment cross-checked against active medications, allergies, and contraindications; unsafe items blocked before output |
| 6 | **Output Synthesis** | Top-5 ranked differential with confidence %, evidence citations, and next steps written as FHIR `DiagnosticReport`; surfaced on physician dashboard |

---

## The LoRA Adapter Trick

Rather than loading four separate 70B models (~160 GB), Shadi loads a single **Meditron-70B** base in FP4 (~38 GB) and hot-swaps four lightweight LoRA adapters (~2 GB each) on top. vLLM supports this natively via `--enable-lora`. The result: four genuinely differentiated specialist models for the memory cost of one.

```
Base model (FP4):   ~38 GB
Cardiology LoRA:     ~2 GB
Neurology LoRA:      ~2 GB
Pulmonology LoRA:    ~2 GB
Toxicology LoRA:     ~2 GB
Evidence + Veto:    ~10 GB  (lighter models)
Orchestrator:        ~4 GB
─────────────────────────
Total:             ~60 GB  (fits in 128 GB unified memory with headroom)
```

This is only possible on a machine with sufficient unified memory — a laptop OOMs at first model load.

---

## Hardware Requirements

| Requirement | Why |
|---|---|
| **128 GB unified memory** | All models + adapters + evidence corpus must be in memory simultaneously for real-time (<2 s) inference |
| **DGX Spark or equivalent** | Only desktop-class machine that meets the memory floor without moving to a data-center GPU |
| **Air-gapped (no cloud API)** | PHI cannot leave the machine; cloud APIs introduce ~200 ms round-trip latency per agent call, killing real-time performance |

A laptop (typically 16–32 GB) OOMs before the first specialist model finishes loading. A cloud API removes the air-gap guarantee required for HIPAA compliance.

---

## Safety Veto — Demo Scenario

The veto's most important moment: **thrombolytics contraindicated in aortic dissection**.

Aortic dissection and STEMI present with overlapping symptoms (chest pain, ST changes). A specialist agent may recommend tPA. Shadi's safety veto agent scans the patient's vitals, imaging flags, and medication context, identifies the aortic dissection risk, and blocks the recommendation with an explicit rationale before output reaches the physician.

This is a documented fatal error pattern in emergency medicine. The veto fires live and the dashboard shows exactly why the recommendation was blocked.

---

## Evaluation Methodology

Shadi is evaluated against **MIMIC-IV de-identified cases**, not just USMLE Q&A benchmarks. USMLE measures recall of medical knowledge; MIMIC-IV measures performance on real patient presentations with the noise, ambiguity, and incomplete information that characterizes actual emergency medicine. Both benchmarks are run; MIMIC-IV is the primary claim.

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- NVIDIA GPU with 128 GB+ unified memory (or DGX Spark)
- Python 3.11+
- `bun` (for dashboard)

### Run

```bash
cp .env.example .env
# Edit .env — set model paths, EHR connection strings, etc.

docker compose up
```

Services:
- `http://localhost:8000` — FastAPI backend
- `http://localhost:3000` — Physician dashboard
- `http://localhost:8080` — vLLM inference server

### Development

```bash
# Python backend
pip install -e ".[dev]"
uvicorn api.main:app --reload

# Dashboard
cd dashboard
bun install
bun dev
```

---

## Directory Structure

```
shadi/
├── agents/
│   ├── base.py                  # BaseAgent ABC
│   ├── intake/                  # Triage note parsing → CaseObject
│   ├── specialists/             # Cardiology, neurology, pulmonology, toxicology
│   ├── evidence/                # PubMed + guidelines cross-reference
│   ├── safety/                  # Safety veto agent
│   └── orchestrator/            # Fan-out, A2A debate, synthesis
├── fhir/                        # FHIR R4 MCP server + resource normalizer
├── a2a/                         # A2A protocol schema + debate round logic
├── models/                      # vLLM engine + LoRA adapter management
├── api/                         # FastAPI app + routes
├── dashboard/                   # Next.js physician dashboard
├── docs/decisions/              # Architecture Decision Records
└── tests/
    ├── fixtures/sample_cases/   # De-identified MIMIC-IV fixtures
    └── unit/
```

---

## Architecture Decision Records

| ADR | Decision |
|---|---|
| [ADR-001](docs/decisions/adr-001-architecture.md) | LoRA adapter strategy, A2A protocol design, air-gap rationale |

---

## Contributing

All architecture decisions must be documented in `docs/decisions/` before implementation. See `docs/decisions/adr-001-architecture.md` for the format.
