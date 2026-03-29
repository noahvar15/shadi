"""OpenAI `model` ids for vLLM chat completions (specialists + claim eval)."""

from __future__ import annotations

import config


def specialist_chat_model(lora_adapter_name: str) -> str:
    """vLLM chat model id for a specialist (LoRA name or base-only override)."""
    override = (config.settings.VLLM_SPECIALIST_MODEL or "").strip()
    return override if override else lora_adapter_name


def claim_eval_chat_model() -> str:
    """vLLM model id for evidence claim evaluation (default matches prior hard-coded id)."""
    override = (config.settings.VLLM_CLAIM_EVAL_MODEL or "").strip()
    return override if override else "meditron:70b"
