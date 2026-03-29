# ADR-004: Serve Meditron-70B for specialists via Ollama (default)

**Date:** 2026-03-29  
**Status:** Accepted

---

## Context

ADR-001/ADR-002 routed the four specialist agents and evidence claim evaluation through **vLLM** so Meditron could be served with **hot-swapped LoRA** adapters per domain. That required local Hugging Face weights, a working vLLM stack (including compatible quantization flags per vLLM version), and operational complexity on developer machines.

The **Ollama library** publishes [`meditron:70b`](https://ollama.com/library/meditron) (quantized GGUF, ~39GB) with an OpenAI-compatible `/v1` API, same as other Shadi Ollama models.

---

## Decision

1. **Specialists ×4** and **evidence claim evaluation** call **`OLLAMA_BASE_URL`** using a single configurable tag, **`MEDITRON_MODEL`** (default **`meditron:70b`**).

2. **Domain differentiation** for specialists remains **prompt- and schema-based only** (cardiology vs neurology system prompts, etc.); there is **no** per-domain weight swap on the default path.

3. **`VLLM_SPECIALIST_MODEL`** and **`VLLM_CLAIM_EVAL_MODEL`** are **removed** from application settings. Optional vLLM + LoRA for research or production-scale deployments is **out of scope** for this codebase path; a future ADR may reintroduce a dual-backend flag if needed.

4. **Docker Compose:** the **`vllm`** service is behind Compose **`profiles: ["vllm-lora"]`** so **`docker compose up`** does not start or wait on vLLM. **`api`** and **`worker`** no longer **`depends_on`** `vllm`. Operators pull Meditron on Ollama, e.g. `docker compose exec ollama ollama pull meditron:70b`.

---

## Consequences

- **Pros:** One inference runtime (Ollama) for all non-vLLM models plus Meditron; simpler local setup; aligns with published `meditron:70b` artifacts.
- **Cons:** No LoRA hot-swap on the default path; clinical differentiation vs the vLLM+LoRA stack is reduced to prompts; Ollama’s Meditron build may differ slightly from EPFL HF checkpoints.

---

## Alternatives considered

- **Keep vLLM as default, Ollama optional:** Rejected for this iteration — user goal is to standardize on Ollama Meditron.
- **Feature flag `USE_VLLM_SPECIALISTS`:** Rejected to avoid dual code paths and test matrices unless a later ADR requires it.
