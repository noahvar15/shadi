"""Tests for Ollama Meditron model tag helpers (ADR-004)."""

from __future__ import annotations

import config
import pytest

from agents.meditron_model_ids import claim_eval_chat_model, specialist_chat_model


def test_specialist_chat_model_uses_meditron_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", config.Settings(MEDITRON_MODEL="meditron:70b"))
    assert specialist_chat_model("cardiology") == "meditron:70b"
    assert specialist_chat_model("neurology") == "meditron:70b"


def test_specialist_chat_model_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config,
        "settings",
        config.Settings(MEDITRON_MODEL="  meditron:70b-q4_0  "),
    )
    assert specialist_chat_model("pulmonology") == "meditron:70b-q4_0"


def test_claim_eval_matches_specialist_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "settings", config.Settings(MEDITRON_MODEL="meditron:70b"))
    assert claim_eval_chat_model() == "meditron:70b"


def test_claim_eval_custom_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config,
        "settings",
        config.Settings(MEDITRON_MODEL="meditron:70b-q4_K_S"),
    )
    assert claim_eval_chat_model() == "meditron:70b-q4_K_S"
