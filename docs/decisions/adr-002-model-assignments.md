# ADR-002: Ollama Model Assignments per Agent

**Date:** 2026-03-28
**Status:** Accepted

---

## Context

The specialist agents (cardiology, neurology, pulmonology, toxicology) are already assigned to `meditron:70b` with domain LoRA adapters served through vLLM (ADR-001). The remaining agents — intake, evidence grounding, safety veto, orchestrator, and image analysis — each have distinct computational profiles. Assigning a single model to all of them wastes VRAM on simple tasks (intake) and under-provisions complex ones (orchestrator synthesis). The DGX Spark's 128 GB unified memory budget allows a purpose-fit model stack.

A second inference server (Ollama) runs alongside vLLM. Both expose an OpenAI-compatible `/v1` API surface, so `BaseAgent.reason()` routes to either endpoint purely via `inference_url` and `model` class attributes — no branching logic in shared code.

---

## Model Assignments

### Image Analysis Agent → `alibayram/medgemma:27b` (Ollama)

**Rationale:** MedGemma 1.5 is Google's multimodal model purpose-built for medical imaging. It handles radiographs, ECGs, chest X-rays, and CT scout images attached to an encounter before the case reaches the specialist agents. No general-purpose vision model approaches its performance on clinical imaging tasks at this parameter count. The Ollama registry tag is `alibayram/medgemma:27b` (the bare `medgemma:27b` library tag does not exist in the Ollama registry).

**Approximate VRAM:** ~17 GB (Q4\_K\_M)

---

### Intake Agent → `qwen2.5:7b` (Ollama)

**Rationale:** Intake is a structured extraction task: parse free-text triage notes and emit SNOMED CT, LOINC, and RxNorm codes into a `CaseObject`. Qwen 2.5 7B leads extraction and structured-output benchmarks at its size class, supports JSON schema mode natively, and adds minimal latency to the pipeline's critical path. Spending 70B parameters on code mapping is not justified.

**Approximate VRAM:** ~4.5 GB (Q4\_K\_M)

---

### Specialist Agents ×4 → `meditron:70b` + LoRA adapters (vLLM)

**Rationale:** Unchanged from ADR-001. Meditron-70B is trained on PubMed and clinical guidelines and outperforms general-purpose 70B models on clinical reasoning benchmarks. vLLM's `--enable-lora` hot-swaps the four domain adapters (cardiology, neurology, pulmonology, toxicology) on a single base model load.

**Approximate VRAM:** ~38 GB base (FP4) + ~8 GB adapters

---

### Evidence Grounding Agent → `nomic-embed-text` + `meditron:70b` (Ollama + vLLM reuse)

**Rationale:** Evidence grounding has two sub-tasks:

1. **Retrieval** — embed specialist claims and query the local PubMed/guidelines vector store (pgvector in Postgres). `nomic-embed-text` is the Ollama-native embedding model: 8192-token context window, MTEB benchmark leader at its size, and ~0.5 GB VRAM.
2. **Claim evaluation** — determine whether retrieved evidence actually supports each specialist finding. This reuses the resident `meditron:70b` endpoint (same vLLM server, no second model load) with an evidence-grounding system prompt. No additional VRAM cost.

**Approximate additional VRAM:** ~0.5 GB (embed model only)

---

### Safety Veto Agent → `phi4:14b` (Ollama)

**Rationale:** The veto's job is logical constraint satisfaction: given proposed recommendations, active medications, allergy records, and contraindication rules, block anything that violates a hard constraint and produce an auditable rationale. Microsoft Phi-4 14B achieves near-70B performance on logical reasoning and instruction-following benchmarks at 14B parameters. Its terse, structured outputs are well-suited to the `VetoDecision` schema. The STEMI/aortic dissection scenario (blocking tPA when aortic dissection cannot be ruled out) is exactly the class of hard-constraint problem Phi-4 was optimised for.

**Approximate VRAM:** ~8 GB (Q4\_K\_M)

---

### Orchestrator / Output Synthesis → `deepseek-r1:32b` (Ollama)

**Rationale:** Synthesis is the most demanding reasoning task in the pipeline: consume `ENDORSE/CHALLENGE/MODIFY` messages from the A2A debate, compute consensus scores, identify divergent diagnoses, rank the top-5 differential with confidence percentages, and write the final FHIR `DiagnosticReport` structure. DeepSeek-R1 32B has chain-of-thought reasoning built into its training objective — it reasons step-by-step before committing to an output. This is the correct fit for reconciling four agents that may partially disagree. It substantially outperforms Llama-class 32B models on multi-step reasoning and structured synthesis, and 32B stays within the VRAM budget.

**Approximate VRAM:** ~19 GB (Q4\_K\_M)

---

## Memory Budget

| Agent | Model | Inference server | Approx VRAM |
|---|---|---|---|
| Image analysis | `alibayram/medgemma:27b` | Ollama | ~17 GB |
| Specialists ×4 (base) | `meditron:70b` FP4 | vLLM | ~38 GB |
| Specialist LoRA adapters ×4 | — | vLLM | ~8 GB |
| Intake | `qwen2.5:7b` | Ollama | ~4.5 GB |
| Evidence (retrieval) | `nomic-embed-text` | Ollama | ~0.5 GB |
| Evidence (claim eval) | `meditron:70b` (reuse) | vLLM | — |
| Safety veto | `phi4:14b` | Ollama | ~8 GB |
| Orchestrator synthesis | `deepseek-r1:32b` | Ollama | ~19 GB |
| **Model subtotal** | | | **~94 GB** |
| OS + Postgres/pgvector + Redis + API + dashboard | | | ~15–20 GB |
| **Grand total** | | | **~109–114 GB** |

The DGX Spark's 128 GB unified memory provides ~14–19 GB headroom for the evidence corpus index and concurrent case load spikes.

---

## Two-Server Strategy

vLLM is kept for Meditron-70B exclusively because Ollama does not support LoRA hot-swapping. All other models are served through Ollama, which handles model lifecycle (pull, unload, concurrent request queuing) without manual weight management. Both servers expose OpenAI-compatible `/v1` endpoints; `BaseAgent` subclasses select the correct server via `inference_url`.

**Alternatives considered:**

- **Ollama for everything:** Would require separate full-weight loads for each specialist domain (~4 × 40 GB = 160 GB), exceeding the 128 GB budget.
- **vLLM for everything:** vLLM's model-switching overhead and lack of a built-in model registry make it cumbersome for the smaller, frequently-swapped models.

---

## Tradeoffs

- Two inference servers to operate and health-check. Mitigated by Docker Compose health checks on both services.
- `deepseek-r1:32b` reasoning traces add ~200–400 ms to synthesis latency. Acceptable given the 30-second end-to-end budget; the thinking trace is discarded before the `DifferentialReport` is written.
- `nomic-embed-text` produces 768-dimensional vectors; pgvector index must be created with `vector(768)`.

---

## Unknowns

- Whether `alibayram/medgemma:27b` multimodal support is stable in the Ollama runtime at the time of deployment; fallback is direct HuggingFace `transformers` inference.
- Whether `deepseek-r1:32b` produces sufficiently deterministic structured output for the FHIR synthesis step, or whether output parsing guard-rails are needed.

---

## Amendment — ADR-004 (2026-03-29)

Specialists ×4 and evidence **claim evaluation** now use **Ollama** with **`MEDITRON_MODEL`** (default `meditron:70b`), not vLLM. Domain differentiation is prompt-based. Optional **vLLM + LoRA** remains available as a Docker Compose **`vllm-lora`** profile for experiments but is **not** wired to agents in the default build. See [ADR-004](adr-004-meditron-via-ollama.md).
