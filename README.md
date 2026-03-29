# Shadi

**Multi-agent clinical diagnostic reasoning system for emergency medicine.**

The **target** pipeline: a case arrives from the EHR via FHIR R4. An **intake** agent (Qwen) can enrich unstructured triage text into coded `CaseObject` fields (SNOMED CT, LOINC, RxNorm). When imaging is attached, a **multimodal imaging** agent (MedGemma — separate from the clinical specialists) interprets those studies. **Four domain specialist agents** — cardiology, neurology, pulmonology, toxicology — each run a domain-specific LoRA adapter on one shared Meditron-70B load in vLLM; they reason in parallel, then **evidence grounding** checks claims against a local PubMed and guidelines corpus. An **orchestrator** runs the structured **A2A** debate (`ENDORSE` / `CHALLENGE` / `MODIFY`), synthesizes consensus and ranked differentials, and a **safety veto** agent blocks unsafe recommendations before anything reaches the physician dashboard or FHIR `DiagnosticReport` output.

What is actually wired today is summarized in [Wiring status (as implemented)](#wiring-status-as-implemented).

---

## Why This Exists

Diagnostic errors in emergency medicine are estimated to affect 12 million patients annually in the US. The window between triage and physician assessment is the highest-leverage moment to surface differential diagnoses that a single clinician might miss under time pressure. Shadi is designed to run in that window — locally, with no PHI leaving the machine.

---

## Architecture

Shadi is a **local, air-gapped** stack: two inference backends (vLLM for Meditron + LoRA specialists, Ollama for every other model), a FastAPI + arq worker surface, Postgres/pgvector for evidence retrieval, Redis for the job queue, and a Next.js physician dashboard. PHI never leaves the machine (see [ADR-001](docs/decisions/adr-001-architecture.md)).

**Specialist count:** exactly **four** LoRA-backed domain agents (cardiology, neurology, pulmonology, toxicology). The imaging agent uses MedGemma on Ollama — it is a multimodal preprocessor-style component, not a fifth LoRA specialist.

### Target architecture (diagram)

The diagram and the [agent pipeline](#agent-pipeline-end-to-end) table describe the **end-state design**. vLLM LoRA modules and ports are defined in `docker-compose.yml` (`vllm` service); specialist routing uses `VLLM_BASE_URL` and adapter names in `agents/specialists/`.

```mermaid
flowchart TD
    EHR["EHR (Epic / Cerner)"]
    MCP["FHIR R4 MCP Server\n(encounter subscription)"]
    Intake["Intake Agent\n(qwen2.5:7b · SNOMED · LOINC · RxNorm)"]
    CaseObj["CaseObject"]

    Img["Imaging Agent\n(MedGemma · optional if attachments)"]

    Cardio["Cardiology\n(LoRA on meditron:70b)"]
    Neuro["Neurology\n(LoRA on meditron:70b)"]
    Pulm["Pulmonology\n(LoRA on meditron:70b)"]
    Tox["Toxicology\n(LoRA on meditron:70b)"]

    Evidence["Evidence Grounding\n(embed + meditron claim eval)"]
    Debate["A2A Debate Round\n(ENDORSE · CHALLENGE · MODIFY)"]
    Orchestrator["Orchestrator synthesis\n(DeepSeek-R1)"]
    Veto["Safety Veto\n(phi4:14b)"]
    Output["DiagnosticReport (FHIR)\n+ Physician Dashboard"]

    EHR --> MCP --> Intake --> CaseObj
    CaseObj --> Img
    CaseObj --> Cardio & Neuro & Pulm & Tox
    Img --> Evidence
    Cardio & Neuro & Pulm & Tox --> Evidence
    Evidence --> Debate --> Orchestrator --> Veto --> Output
```

### Agent pipeline (end-to-end)

| Stage | Component | Responsibility |
|---|---|---|
| 0 | **EHR → MCP** | Subscribe to encounters; deliver FHIR R4 bundles into the app |
| 1 | **Intake** | Parse unstructured triage notes; extract SNOMED CT, LOINC, RxNorm codes; build `CaseObject` |
| 2a | **Imaging (optional)** | If `imaging_attachments` exist, MedGemma interprets images; outputs structured findings (skipped when no attachments) |
| 2b | **Specialists ×4 (LoRA)** | Cardiology, neurology, pulmonology, toxicology on shared `meditron:70b` with per-domain LoRA; reason concurrently; no cross-talk until debate |
| 3 | **Evidence grounding** | Retrieve from local vector index; evaluate whether evidence supports each claim (embedding model + Meditron reuse for claim eval) |
| 4 | **A2A debate** | Structured `ENDORSE / CHALLENGE / MODIFY` messages; orchestrator records consensus and divergence |
| 5 | **Orchestrator synthesis** | Rank differential, confidence scores, reconcile disagreement (dedicated reasoning model — ADR-002) |
| 6 | **Safety veto** | Cross-check diagnostics and treatments vs meds, allergies, contraindications; block unsafe items |
| 7 | **Output** | Top-ranked differential with evidence ties; FHIR `DiagnosticReport`; physician dashboard |

### Wiring status (as implemented)

- **Case intake:** `POST /cases` builds a `CaseObject` from the FHIR R4 bundle via `FHIRNormalizer.bundle_to_case` (`CaseObject.from_fhir_bundle` in `agents/schemas.py`). The LLM **IntakeAgent** (`qwen2.5:7b`) exists under `agents/intake/` and is covered by unit tests, but it is **not** called from `POST /cases` or from `Orchestrator.run()` yet.
- **Diagnostic jobs:** The **`worker`** service runs arq `tasks.pipeline.run_diagnostic_pipeline`, which loads the case from Postgres and calls `Orchestrator().run(case)`. The orchestrator runs **four LoRA specialists** → evidence grounding → A2A debate → orchestrator synthesis → safety veto. **ImageAnalysisAgent** (MedGemma) exists under `agents/specialists/image_agent.py` and is tested in isolation, but it is **not** invoked inside `Orchestrator.run()` yet.
- **FHIR Subscription rest-hook:** Inbound notifications are handled by **`POST /fhir/notify`** on the **api** process (port **8000**), not a separate container. Configure `NOTIFICATION_ENDPOINT`, `FHIR_WEBHOOK_SECRET`, and related vars per `.env.example` when MCP is enabled.
- **Local EHR for #26 / #27:** The in-repo **mock EHR** (`python -m tools.mock_ehr`) implements OAuth token, `Subscription`, and a demo rest-hook to Shadi. See [tools/mock_ehr/README.md](tools/mock_ehr/README.md). It is run **beside** Compose, not included in the default `docker compose up` profile.

---

## Model Stack

Two inference servers run side-by-side. vLLM handles the specialists (LoRA hot-swap required); Ollama handles everything else. Both expose an OpenAI-compatible `/v1` API — agents route to the correct server via `inference_url` and `model` class attributes. See [ADR-002](docs/decisions/adr-002-model-assignments.md) for full rationale.

| Agent | Model | Server | Approx VRAM |
|---|---|---|---|
| Image analysis | `alibayram/medgemma:27b` | Ollama | ~17 GB |
| Intake | `qwen2.5:7b` | Ollama | ~4.5 GB |
| Specialists ×4 (base) | `meditron:70b` FP4 | vLLM | ~38 GB |
| Specialist LoRA adapters ×4 | cardiology / neurology / pulmonology / toxicology | vLLM | ~8 GB |
| Evidence (retrieval) | `nomic-embed-text` | Ollama | ~0.5 GB |
| Evidence (claim eval) | `meditron:70b` (reuse) | vLLM | — |
| Safety veto | `phi4:14b` | Ollama | ~8 GB |
| Orchestrator synthesis | `deepseek-r1:32b` | Ollama | ~19 GB |
| **Model subtotal** | | | **~94 GB** |
| OS + services | | | ~15–20 GB |
| **Grand total** | | | **~109–114 GB** |

The DGX Spark's 128 GB unified memory leaves ~14–19 GB headroom for the evidence corpus index and concurrent case spikes. A laptop OOMs before the first specialist model finishes loading.

### The LoRA Adapter Trick

The four specialist agents share a single `meditron:70b` base load in FP4 (~38 GB). vLLM hot-swaps a domain LoRA adapter (~2 GB each) per request via `--enable-lora`. The result: four genuinely differentiated clinical specialists for the memory cost of one model. Loading four separate 70B weights would require ~160 GB — exceeding the hardware budget entirely.

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
# Edit .env — set model paths, EHR connection strings, MOCK_LLM=false for real inference, etc.

docker compose up
```

Agents use the root [`config.py`](config.py) flag **`MOCK_LLM`** (default **`true`**): when true, LLM calls short-circuit to deterministic stubs so the stack runs without downloaded weights. Set **`MOCK_LLM=false`** in `.env` when Ollama and vLLM are up and models are pulled.

On first boot, pull the Ollama models (vLLM loads Meditron from the path in `.env`):

```bash
docker exec shadi-ollama-1 ollama pull alibayram/medgemma:27b
docker exec shadi-ollama-1 ollama pull qwen2.5:7b
docker exec shadi-ollama-1 ollama pull nomic-embed-text
docker exec shadi-ollama-1 ollama pull phi4:14b
docker exec shadi-ollama-1 ollama pull deepseek-r1:32b
```

Services (Compose):
- `http://localhost:8000` — FastAPI **api** (includes **`POST /fhir/notify`** for Subscription rest-hook when configured)
- `http://localhost:3000` — Physician dashboard
- `http://localhost:8080` — vLLM (meditron:70b + LoRA)
- `http://localhost:11434` — Ollama (all non-specialist models)
- **`worker`** — arq consumer for `tasks.pipeline.run_diagnostic_pipeline` (no extra HTTP port)

For **OAuth + FHIR Subscription + rest-hook** (#26–#27), default Compose does not bundle a reference FHIR server. Use the in-repo **mock EHR**: [`tools/mock_ehr/README.md`](tools/mock_ehr/README.md) (`python -m tools.mock_ehr`, default port 9001). Optional Dockerized HAPI (or similar) remains future work; see [`docs/cross-track-dependencies.md`](docs/cross-track-dependencies.md) (*Local FHIR or EHR stub (#25)*).

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
│   ├── intake/                  # IntakeAgent (Qwen) — see Wiring status
│   ├── specialists/             # Four LoRA specialists + image_agent (MedGemma)
│   ├── evidence/                # PubMed + guidelines cross-reference
│   ├── safety/                  # Safety veto agent
│   └── orchestrator/            # Fan-out, A2A debate, synthesis
├── shadi_fhir/                  # FHIR R4 normalizer + MCP (OAuth #26, Subscription/notify #27, teardown #29)
├── a2a/                         # A2A protocol schema + debate round logic
├── api/                         # FastAPI app + routes (incl. POST /fhir/notify)
├── tasks/                       # arq worker + pipeline job
├── tools/
│   └── mock_ehr/                # Local mock EHR for OAuth + Subscription + rest-hook demos
├── dashboard/                   # Next.js physician dashboard
├── skills/                      # Shared Cursor/agent skills (see AGENTS.md)
├── scripts/                     # Repo maintenance scripts
├── docs/decisions/              # Architecture Decision Records
├── config.py                    # Agent settings (MOCK_LLM, inference URLs)
├── docker-compose.yml           # vLLM + Ollama + api + worker + postgres + redis + dashboard
├── pyproject.toml
└── tests/
    ├── fixtures/                # FHIR bundles, report JSON for tests
    └── unit/
```

---

## Architecture Decision Records

| ADR | Decision |
|---|---|
| [ADR-001](docs/decisions/adr-001-architecture.md) | LoRA adapter strategy, A2A protocol design, air-gap rationale |
| [ADR-002](docs/decisions/adr-002-model-assignments.md) | Ollama model assignments per agent, two-server strategy, memory budget |

---

## Contributing

All architecture decisions must be documented in `docs/decisions/` before implementation. See `docs/decisions/adr-001-architecture.md` for the format.
