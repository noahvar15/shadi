# ADR-003: vLLM base-only mode for local development

**Date:** 2026-03-29  
**Status:** Accepted

---

## Context

Production Shadi serves four specialist agents via vLLM with `--enable-lora` and four on-disk LoRA checkpoints (ADR-001). Those adapters are not shipped in the repository; developers may have only the Meditron-70B base weights while adapter training or packaging is in progress.

Starting vLLM with `--lora-modules` pointing at missing or empty directories fails. Developers still need to run the stack against a single served base model for integration testing.

---

## Decision

1. **Optional Compose merge file** `docker-compose.vllm-base.yml` overrides the `vllm` service to start **without** LoRA flags or adapter mounts — only the base model path, same FP4 and port as the default service.

2. **Environment overrides** on the application side:
   - `VLLM_SPECIALIST_MODEL` — when non-empty, all four specialists use this OpenAI `model` id for `/v1/chat/completions` instead of the per-domain LoRA names (`cardiology`, etc.). Agent metadata (`describe()`, logs) still reports the logical LoRA/domain id.
   - `VLLM_CLAIM_EVAL_MODEL` — when non-empty, the evidence agent’s claim-evaluation call uses this id instead of the default `meditron:70b`.

3. **Verification script** `scripts/verify_lora_adapters.sh` checks that `LORA_ADAPTERS_PATH` contains the four expected subdirectories before starting full LoRA mode.

---

## Consequences

- **Pros:** Stack can boot with base-only vLLM; specialists and claim eval align with whatever model id the running vLLM instance exposes (`GET /v1/models`).
- **Cons:** Without LoRAs, specialists are not domain-differentiated at the weight level — only prompts differ. This is acceptable for wiring tests, not for clinical evaluation.

---

## Alternatives considered

- **Placeholder dummy LoRA directories:** Would still require valid adapter files or risk vLLM startup failures; rejected.
- **Separate “mock vLLM” container:** Extra maintenance; merge file + env is simpler.
