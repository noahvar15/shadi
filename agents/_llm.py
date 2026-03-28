"""Shared async helper for OpenAI-compatible chat completions.

All agents funnel their inference calls through ``call_chat``. When
``settings.MOCK_LLM`` is ``True`` (the default for local development), the
function returns a hardcoded fixture keyed by ``mock_domain`` so the rest of
the pipeline can be exercised without downloaded models.

Migration to live inference
---------------------------
Set ``MOCK_LLM=false`` in ``.env`` (or the process environment). No agent
code needs to change — ``call_chat`` will forward requests to the appropriate
OpenAI-compatible ``/v1/chat/completions`` endpoint automatically.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from config import settings

# Reused across live (non-mock) chat calls to avoid per-request TCP setup.
_shared_http_client: httpx.AsyncClient | None = None


async def _get_shared_http_client() -> httpx.AsyncClient:
    global _shared_http_client
    if _shared_http_client is None:
        _shared_http_client = httpx.AsyncClient(
            timeout=120.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
    return _shared_http_client


async def aclose_shared_llm_http_client() -> None:
    """Close the shared HTTP client (optional — e.g. tests or graceful shutdown)."""
    global _shared_http_client
    if _shared_http_client is not None:
        await _shared_http_client.aclose()
        _shared_http_client = None


# ── Mock fixtures ─────────────────────────────────────────────────────────────
# Keyed by the ``mock_domain`` hint passed by each agent. These are minimal
# but structurally valid responses so downstream parsing succeeds.

_MOCK_RESPONSES: dict[str, str] = {
    "intake": json.dumps(
        {
            "conditions": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "73211009",
                    "display": "Diabetes mellitus (mock)",
                }
            ],
            "observations": [
                {
                    "loinc_code": "2339-0",
                    "display": "Glucose [Mass/volume] in Blood (mock)",
                    "value": 180,
                    "unit": "mg/dL",
                }
            ],
            "medications": [
                {
                    "rxnorm_code": "860975",
                    "name": "Metformin 500 mg oral tablet (mock)",
                }
            ],
        }
    ),
    "imaging": json.dumps(
        {
            "diagnoses": [
                {
                    "rank": 1,
                    "display": "No acute cardiopulmonary process (mock)",
                    "confidence": 0.85,
                    "flags": ["MOCK"],
                }
            ],
            "reasoning_trace": "Mock imaging analysis — no real model was called.",
        }
    ),
    "cardiology": json.dumps(
        {
            "diagnoses": [
                {
                    "rank": 1,
                    "snomed_code": "57054005",
                    "display": "Acute myocardial infarction (mock)",
                    "confidence": 0.60,
                    "flags": ["MOCK"],
                },
                {
                    "rank": 2,
                    "snomed_code": "59282003",
                    "display": "Pulmonary embolism (mock)",
                    "confidence": 0.25,
                    "flags": ["MOCK"],
                },
            ],
            "reasoning_trace": "Mock cardiology reasoning — no real model was called.",
        }
    ),
    "neurology": json.dumps(
        {
            "diagnoses": [
                {
                    "rank": 1,
                    "snomed_code": "230690007",
                    "display": "Cerebrovascular accident (mock)",
                    "confidence": 0.55,
                    "flags": ["MOCK"],
                },
                {
                    "rank": 2,
                    "snomed_code": "266257000",
                    "display": "Transient ischaemic attack (mock)",
                    "confidence": 0.30,
                    "flags": ["MOCK"],
                },
            ],
            "reasoning_trace": "Mock neurology reasoning — no real model was called.",
        }
    ),
    "pulmonology": json.dumps(
        {
            "diagnoses": [
                {
                    "rank": 1,
                    "snomed_code": "233726005",
                    "display": "Pneumonia (mock)",
                    "confidence": 0.65,
                    "flags": ["MOCK"],
                },
                {
                    "rank": 2,
                    "snomed_code": "195967001",
                    "display": "COPD exacerbation (mock)",
                    "confidence": 0.20,
                    "flags": ["MOCK"],
                },
            ],
            "reasoning_trace": "Mock pulmonology reasoning — no real model was called.",
        }
    ),
    "toxicology": json.dumps(
        {
            "diagnoses": [
                {
                    "rank": 1,
                    "snomed_code": "75478009",
                    "display": "Drug overdose (mock)",
                    "confidence": 0.70,
                    "flags": ["MOCK"],
                },
                {
                    "rank": 2,
                    "snomed_code": "403824003",
                    "display": "Drug interaction effect (mock)",
                    "confidence": 0.20,
                    "flags": ["MOCK"],
                },
            ],
            "reasoning_trace": "Mock toxicology reasoning — no real model was called.",
        }
    ),
    # Claim evaluation response used by EvidenceAgent when calling meditron:70b.
    # In practice MOCK_LLM short-circuits before claim eval is ever reached, but
    # the entry is here so tests can patch call_chat and get a deterministic reply.
    "evidence": json.dumps(
        {
            "verdict": "SUPPORTS",
            "explanation": "Mock claim evaluation — no real model was called.",
        }
    ),
    # Safety veto response used by SafetyVetoAgent when calling phi4:14b.
    # In practice MOCK_LLM short-circuits before call_chat is reached, but
    # the entry is here so tests can patch call_chat and get a deterministic reply.
    "safety": json.dumps(
        {
            "decisions": [
                {
                    "recommendation": "Mock recommendation",
                    "vetoed": False,
                    "reason": None,
                    "contraindication_codes": [],
                }
            ]
        }
    ),
}

_MOCK_FALLBACK = json.dumps(
    {"diagnoses": [], "reasoning_trace": "Mock response — unknown domain."}
)


async def call_chat(
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    response_format: dict[str, str] | None = None,
    mock_domain: str = "",
) -> str:
    """POST to an OpenAI-compatible ``/v1/chat/completions`` endpoint.

    Parameters
    ----------
    base_url:
        Root URL of the inference server (e.g. ``http://localhost:11434/v1``).
    model:
        Model name or LoRA adapter identifier passed as ``"model"`` in the
        request body.
    messages:
        List of ``{"role": ..., "content": ...}`` dicts.
    response_format:
        Optional ``{"type": "json_object"}`` for JSON-mode responses.
    mock_domain:
        Key into ``_MOCK_RESPONSES`` used when ``settings.MOCK_LLM`` is
        ``True``. Pass the agent's domain string (e.g. ``"intake"``).

    Returns
    -------
    str
        The raw text content of the first assistant message.
    """
    if settings.MOCK_LLM:
        return _MOCK_RESPONSES.get(mock_domain, _MOCK_FALLBACK)

    payload: dict[str, Any] = {"model": model, "messages": messages}
    if response_format is not None:
        payload["response_format"] = response_format

    client = await _get_shared_http_client()
    resp = await client.post(f"{base_url}/chat/completions", json=payload)
    resp.raise_for_status()
    data = resp.json()
    return str(data["choices"][0]["message"]["content"])
