# Shadi

**Multi-agent clinical diagnostic reasoning system for emergency medicine.**

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
# Edit .env — set model paths, EHR connection strings, etc.

docker compose up
```

On first boot, pull the Ollama models (vLLM loads Meditron from the path in `.env`):

```bash
docker exec shadi-ollama-1 ollama pull alibayram/medgemma:27b
docker exec shadi-ollama-1 ollama pull qwen2.5:7b
docker exec shadi-ollama-1 ollama pull nomic-embed-text
docker exec shadi-ollama-1 ollama pull phi4:14b
docker exec shadi-ollama-1 ollama pull deepseek-r1:32b
```

Services:
- `http://localhost:8000` — FastAPI backend
- `http://localhost:3000` — Physician dashboard
- `http://localhost:8080` — vLLM inference server (meditron:70b + LoRA)
- `http://localhost:11434` — Ollama inference server (all other models)

### vLLM without LoRA adapters (development)

The default Compose file starts vLLM with four LoRA module paths. If those directories are missing, use the merge file from [ADR-003](docs/decisions/adr-003-vllm-base-only-development.md):

```bash
docker compose -f docker-compose.yml -f docker-compose.vllm-base.yml up -d vllm
```

After the server is healthy, discover the OpenAI model id and set it in `.env`:

```bash
curl -s http://localhost:8080/v1/models
```

Set `VLLM_SPECIALIST_MODEL` and `VLLM_CLAIM_EVAL_MODEL` to that id (often the same string vLLM lists for the loaded checkpoint). Specialists still use domain-specific prompts; only the served weights are shared.

To confirm LoRA layout before using the default vLLM service:

```bash
chmod +x scripts/verify_lora_adapters.sh
./scripts/verify_lora_adapters.sh
```

**`verify_lora_adapters.sh` exits 0 only when the layout is valid; otherwise it exits 1.** Until then, pick one:

1. **Full LoRA** — Set `LORA_ADAPTERS_PATH` in `.env` to a directory that contains `cardiology/`, `neurology/`, `pulmonology/`, and `toxicology/` with real adapter checkpoints (create that tree or reuse an existing one).
2. **No LoRA yet** — Use `docker-compose.vllm-base.yml`, set `VLLM_SPECIALIST_MODEL` and `VLLM_CLAIM_EVAL_MODEL` from `GET /v1/models` ([ADR-003](docs/decisions/adr-003-vllm-base-only-development.md)); do not rely on default Compose `vllm` `--lora-modules` until adapters exist.

### Full case output (Docker Compose — real models + DB)

Use this when you want **vLLM, Ollama, Postgres, Redis, API, and the arq worker** all running and a **complete diagnostic report** (not `MOCK_LLM`).

**1. Configure `.env` (from `.env.example`)**

- Set **`MOCK_LLM=false`** so the API/worker call real inference.
- Set **`MODEL_BASE_PATH`** and **`LORA_ADAPTERS_PATH`** to your Meditron base weights and four LoRA dirs (or use [ADR-003](docs/decisions/adr-003-vllm-base-only-development.md) base-only Compose + `VLLM_SPECIALIST_MODEL` / `VLLM_CLAIM_EVAL_MODEL`).
- Set a real **`API_SECRET_KEY`** (not a placeholder).
- Ensure **`EVIDENCE_INDEX_PATH`** on the host exists and points at your evidence index (Compose mounts it read-only into the API). Create an empty directory if you only need the stack to start; evidence quality depends on a real index.
- Leave **`DATABASE_URL`** in `.env` as localhost for host-side tools; **Compose overrides** `DATABASE_URL`, `VLLM_BASE_URL`, and `OLLAMA_BASE_URL` inside `api` / `worker` automatically.

**2. LoRA layout (skip if using `docker-compose.vllm-base.yml`)**

```bash
./scripts/verify_lora_adapters.sh
```

**3. Start the stack**

```bash
docker compose up -d
```

Wait until `postgres`, `redis`, `vllm`, `ollama`, `api`, and `worker` are healthy (`docker compose ps`).

**4. Pull Ollama models (first time only)**

```bash
docker compose exec ollama ollama pull alibayram/medgemma:27b
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec ollama ollama pull phi4:14b
docker compose exec ollama ollama pull deepseek-r1:32b
```

**5. Smoke-check inference**

```bash
curl -sf http://localhost:8080/health
curl -sf http://localhost:11434/api/tags
curl -sf http://localhost:8000/health
```

**6. Enqueue a case and read the report**

Full **`CaseObject` from FHIR** (requires a valid bundle for your normalizer), or temporarily **`SHADI_STUB_CASE_INTAKE=1`** in `.env` with any JSON body for a stub case (restart `api` + `worker` after changing `.env`).

```bash
# Example: POST a bundle (adjust path if not run from repo root)
RESP=$(curl -s -X POST http://localhost:8000/cases \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_bundle.json)
echo "$RESP"
CASE_ID=$(echo "$RESP" | python3 -c "import sys, json; print(json.load(sys.stdin)['case_id'])")

# Poll until complete (pipeline runs in the worker)
while true; do
  STATUS=$(curl -s "http://localhost:8000/reports/${CASE_ID}/status" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status',''))")
  echo "status=$STATUS"
  [ "$STATUS" = "complete" ] && break
  sleep 3
done

curl -s "http://localhost:8000/reports/${CASE_ID}" | python3 -m json.tool
```

If `sample_bundle.json` returns **422**, the normalizer rejected it — use a bundle that matches `CaseObject.from_fhir_bundle` or enable **`SHADI_STUB_CASE_INTAKE=1`** for an end-to-end wiring check.

**7. Optional: live orchestrator on the host (same models as `.env`)**

Requires **Postgres and inference reachable from the host** (`localhost:5432`, `8080`, `11434`) and **`.venv`** with the package installed:

```bash
export MOCK_LLM=false
.venv/bin/python tests/integration/run_live_cli.py
```

### Development

Many Linux images ship **`python3`** only (no `python` on `PATH`). Use **`python3`** and a project venv so `pytest` and Shadi share one interpreter:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Tests (works without activating the venv)
./scripts/run_tests.sh
# Or: .venv/bin/python -m pytest tests/ -q

# Multi-agent CLI demo (mock LLM; no vLLM/Ollama). With a repo ``.venv``,
# ``python3 -m tools.shadi_run_case_cli`` re-runs under ``.venv/bin/python``.
python3 -m tools.shadi_run_case_cli

# Same pipeline against **real** vLLM + Ollama (``MOCK_LLM=false`` in a subprocess only;
# slow, requires models up — see ADR-002):
# .venv/bin/python -m pytest tests/integration/test_shadi_live_cli_output.py --live-inference -s

# API locally
.venv/bin/uvicorn api.main:app --reload
```

```bash
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
├── shadi_fhir/                  # FHIR R4 normalizer + MCP (OAuth #26, Subscription/notify #27, teardown #29)
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
| [ADR-002](docs/decisions/adr-002-model-assignments.md) | Ollama model assignments per agent, two-server strategy, memory budget |
| [ADR-003](docs/decisions/adr-003-vllm-base-only-development.md) | Optional base-only vLLM Compose merge + env overrides when LoRAs are absent |

---

## Contributing

All architecture decisions must be documented in `docs/decisions/` before implementation. See `docs/decisions/adr-001-architecture.md` for the format.
