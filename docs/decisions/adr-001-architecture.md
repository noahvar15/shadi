# ADR-001: Core Architecture Decisions

**Date:** 2026-03-28
**Status:** Accepted

---

## Context

Shadi needs to run four domain-specialist LLM agents concurrently, cross-reference their outputs against a clinical evidence corpus, conduct a structured inter-agent debate, apply a safety veto, and write a FHIR DiagnosticReport — all within the window between patient triage and physician room entry (target: <30 seconds end-to-end). It must do this entirely on a local machine with no PHI leaving the device.

---

## Decision 1: Single base model with LoRA adapters per specialist

**Decision:** Load one Meditron-70B base model in FP4 quantization and hot-swap four lightweight LoRA adapters (cardiology, neurology, pulmonology, toxicology) rather than loading four separate 70B models.

**Why:** Four separate 70B models in FP4 would require ~160 GB. The DGX Spark has 128 GB unified memory. LoRA adapters are ~2 GB each; the total memory footprint drops to ~50-60 GB, leaving headroom for the evidence agent, safety veto model, orchestrator, and the OS.

**Alternatives considered:**
- Four separate smaller models (e.g. 7B per specialist): Lower total memory, but 7B models lack the clinical reasoning depth needed for the evidence-grounding and debate rounds. Meditron is fine-tuned on PubMed + clinical guidelines and outperforms general 70B on clinical benchmarks.
- Mixture-of-experts (MoE) single model: Available MoE models lack domain-specific clinical fine-tuning at the quality level of Meditron-70B. LoRA adapters on a strong base offer more control over specialist behavior.

**Tradeoffs:**
- LoRA adapters must be trained or fine-tuned per domain — this is ongoing work, not a one-time cost.
- Hot-swapping adapters per request adds ~50 ms latency per specialist call. Acceptable given the 30-second budget.
- vLLM's `--enable-lora` flag is required; not all inference servers support this.

**Unknowns:**
- Quality of available open cardiology/neurology/pulmonology/toxicology LoRA adapters. We may need to fine-tune from a base Meditron checkpoint.
- Whether FP4 quantization degrades clinical reasoning on edge cases (rare presentations) relative to FP8 or BF16.

---

## Decision 2: A2A debate protocol using structured messages (ENDORSE / CHALLENGE / MODIFY)

**Decision:** Implement agent-to-agent debate as a structured message-passing protocol with three explicit intents (`ENDORSE`, `CHALLENGE`, `MODIFY`) rather than freeform LLM-to-LLM conversation.

**Why:** Freeform multi-agent conversation is non-deterministic and hard to audit. In a clinical context, every disagreement between agents must be traceable and explainable. Structured messages allow the orchestrator to compute consensus scores algorithmically, surface divergence clearly to the physician, and produce an audit trail.

**Alternatives considered:**
- Freeform LLM dialogue: Higher expressiveness, but produces unstructured output that is difficult to parse into ranked diagnoses with confidence scores.
- Voting-only (no debate): Simpler, but misses the case where one agent has a strong, evidence-backed objection that should override a majority consensus.

**Tradeoffs:**
- Structured schema constrains what agents can express. Complex multi-step arguments must be compressed into a single `argument` string.
- Schema evolution (adding new intent types) requires coordinated changes across all agent implementations.

**Unknowns:**
- Optimal number of debate rounds. One round is implemented; empirical testing on MIMIC-IV cases will determine whether two rounds improve accuracy.

---

## Decision 3: FHIR R4 MCP server for EHR ingestion

**Decision:** Implement EHR ingestion as a FHIR R4 MCP (Model Context Protocol) server that subscribes to encounter events from Epic/Cerner rather than polling the EHR REST API or using a custom integration layer.

**Why:** MCP provides a standardized protocol for exposing structured resources to LLM agents. FHIR R4 is the mandated interoperability standard in the US under ONC rules (21st Century Cures Act). Using FHIR natively means the output DiagnosticReport can be written back to the EHR without a translation layer.

**Alternatives considered:**
- Custom EHR connector per vendor: Higher fidelity for specific EHR quirks, but non-portable and requires separate maintenance per hospital.
- HL7 v2 messaging: Widely deployed but significantly more complex to parse than FHIR resources; SNOMED/LOINC codes are not guaranteed in v2 messages.

**Tradeoffs:**
- FHIR subscription support varies by EHR vendor and version. Epic FHIR R4 is well-supported; some Cerner versions require specific configuration.
- SMART on FHIR OAuth2 adds authentication complexity that must be handled before any data flows.

**Unknowns:**
- Whether target hospital's Epic/Cerner instance has FHIR subscriptions enabled and what events are available.
- Latency of FHIR subscription delivery vs. real-time triage events — may require a fallback polling approach.

---

## Decision 4: Air-gapped operation (no cloud API calls)

**Decision:** All inference runs locally on the DGX Spark. No patient data is sent to any external API.

**Why:** HIPAA prohibits PHI transmission to third parties without a BAA. Even with a BAA, cloud API round-trips (~200 ms per call × 6+ agent calls) would exceed the real-time performance budget. Air-gap is both a compliance requirement and a performance requirement.

**Alternatives considered:**
- Cloud inference with PHI de-identification before transmission: De-identification is error-prone and de-identified data may still be re-identifiable via rare conditions or timestamps. Not acceptable for a clinical tool.
- Hybrid (PHI local, non-PHI cloud): Increases architectural complexity with marginal benefit.

**Tradeoffs:**
- Entire model stack must be maintained on-premises, including updates to Meditron weights and LoRA adapters.
- No access to frontier models (GPT-4o, Claude) that may outperform Meditron on some cases.

**Unknowns:**
- Whether Meditron-70B + domain LoRA adapters will match frontier model performance on rare presentations. The MIMIC-IV eval will provide the first data point.

---

## Decision 5: FastAPI + asyncio for the backend

**Decision:** Python FastAPI with async handlers and asyncio-based agent orchestration.

**Why:** The agent fan-out pattern (4 specialists running concurrently) is a natural fit for asyncio's `gather`. FastAPI's async support, Pydantic v2 integration, and OpenAPI generation align well with the FHIR/Pydantic data model already in use. The team is Python-primary, which matches the ML/inference stack.

**Alternatives considered:**
- Go or Rust service: Better raw performance, but the inference bottleneck is the GPU, not the orchestration layer. Python keeps the stack uniform.
- Celery + synchronous workers: Heavier infrastructure for what is fundamentally a fan-out/fan-in async pattern.

**Tradeoffs:**
- Python GIL limits true parallelism for CPU-bound work, but agent `reason()` calls are I/O-bound (HTTP to vLLM), so asyncio is appropriate.
- asyncio error handling is more complex than synchronous code; agent failures must be caught and reported without killing the entire pipeline.

**Unknowns:**
- Whether asyncio's concurrency model is sufficient at scale (multiple simultaneous cases) or whether a process-based model (e.g., Ray) will be needed.
