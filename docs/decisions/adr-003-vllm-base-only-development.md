# ADR-003: vLLM base-only mode for local development

**Date:** 2026-03-29  
**Status:** Accepted (optional stack only — application specialists use Ollama Meditron per **ADR-004**)

---

## Context

Historically, production Shadi could serve specialist agents via vLLM with `--enable-lora` and four on-disk LoRA checkpoints (ADR-001). Those adapters are not shipped in the repository; developers may have only the Meditron-70B base weights while adapter training or packaging is in progress.

Starting vLLM with `--lora-modules` pointing at missing or empty directories fails. Developers still need to run the stack against a single served base model for integration testing.

---

## Decision

1. **Optional Compose merge file** `docker-compose.vllm-base.yml` overrides the `vllm` service to start **without** LoRA flags or adapter mounts — only the base model path, same FP4 and port as the default service.

2. **Environment overrides (historical):** ADR-003 originally specified `VLLM_SPECIALIST_MODEL` / `VLLM_CLAIM_EVAL_MODEL`; **ADR-004 removed these from application settings.** The optional vLLM container no longer has a first-class wiring path in agent code.

3. **Verification script** `scripts/verify_lora_adapters.sh` checks that `LORA_ADAPTERS_PATH` contains the four expected subdirectories before starting full LoRA mode.

4. **Base weights preflight** `scripts/check_vllm_model_base.sh` checks that `MODEL_BASE_PATH` contains `config.json` (Hugging Face) or `params.json` (Mistral) so vLLM does not fail at startup with an invalid `/models/base` mount.

---

## Consequences

- **Pros:** Stack can boot with base-only vLLM; specialists and claim eval align with whatever model id the running vLLM instance exposes (`GET /v1/models`).
- **Cons:** Without LoRAs, specialists are not domain-differentiated at the weight level — only prompts differ. This is acceptable for wiring tests, not for clinical evaluation.

---

## Alternatives considered

- **Placeholder dummy LoRA directories:** Would still require valid adapter files or risk vLLM startup failures; rejected.
- **Separate “mock vLLM” container:** Extra maintenance; merge file + env is simpler.
