"""Ollama `model` tag for Meditron (specialists + evidence claim eval). See ADR-004."""

from __future__ import annotations

import config


def specialist_chat_model(_logical_domain_id: str) -> str:
    """OpenAI `model` id for a specialist chat call.

    *logical_domain_id* is the historical LoRA/domain label (e.g. ``cardiology``);
    all specialists share ``MEDITRON_MODEL`` on Ollama.
    """
    _ = _logical_domain_id
    return (config.settings.MEDITRON_MODEL or "meditron:70b").strip()


def claim_eval_chat_model() -> str:
    """OpenAI `model` id for evidence claim evaluation."""
    return (config.settings.MEDITRON_MODEL or "meditron:70b").strip()
