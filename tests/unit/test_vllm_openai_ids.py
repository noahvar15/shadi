"""vLLM OpenAI model id helpers (ADR-003)."""

from __future__ import annotations

import pytest

import config
from agents.vllm_openai_ids import claim_eval_chat_model, specialist_chat_model


def test_specialist_chat_model_default_uses_lora_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", config.Settings(VLLM_SPECIALIST_MODEL=""))
    assert specialist_chat_model("cardiology") == "cardiology"


def test_specialist_chat_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config,
        "settings",
        config.Settings(VLLM_SPECIALIST_MODEL=" /models/base "),
    )
    assert specialist_chat_model("cardiology") == "/models/base"


def test_claim_eval_chat_model_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", config.Settings(VLLM_CLAIM_EVAL_MODEL=""))
    assert claim_eval_chat_model() == "meditron:70b"


def test_claim_eval_chat_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config,
        "settings",
        config.Settings(VLLM_CLAIM_EVAL_MODEL="my-base"),
    )
    assert claim_eval_chat_model() == "my-base"
