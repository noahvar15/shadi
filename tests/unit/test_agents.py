"""Unit tests for all six agent classes.

All tests run against mock LLM responses (MOCK_LLM=True is the default in
config.py). No models need to be downloaded; no inference servers need to be
running.

Coverage:
  - BaseAgent.describe() contract for all six agents
  - inference_url routing: Ollama for intake/image, vLLM for specialists
  - IntakeAgent.run() populates case.conditions / observations / medications
  - ImageAnalysisAgent early-exit when imaging_attachments is empty
  - ImageAnalysisAgent returns diagnoses when attachments are present
  - All specialist agents return SpecialistResult with domain set correctly
  - DiagnosisCandidate confidence values sum ≤ 1.0 for every specialist
  - Custom mock: overriding call_chat to test specific payloads
  - Custom mock: handling of partial/missing JSON keys
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from agents.intake.intake_agent import IntakeAgent
from agents.schemas import CaseObject, SpecialistResult
from agents.specialists.cardiology_agent import CardiologyAgent
from agents.specialists.image_agent import ImageAnalysisAgent
from agents.specialists.neurology_agent import NeurologyAgent
from agents.specialists.pulmonology_agent import PulmonologyAgent
from agents.specialists.toxicology_agent import ToxicologyAgent
from config import settings

# ── Shared test fixture ───────────────────────────────────────────────────────

MOCK_CASE = CaseObject(
    patient_id="P001",
    encounter_id="E001",
    chief_complaint="chest pain and shortness of breath",
    triage_notes_raw=(
        "68yo M with sudden onset chest pain, diaphoresis, BP 90/60. "
        "Taking metformin 500 mg daily for diabetes."
    ),
    age=68,
    sex="male",
)


def fresh_case(**overrides) -> CaseObject:
    """Return a deep copy of MOCK_CASE with optional field overrides."""
    return MOCK_CASE.model_copy(update=overrides, deep=True)


# ── describe() contract ───────────────────────────────────────────────────────


def test_all_agents_have_describe():
    agents = [
        IntakeAgent(),
        ImageAnalysisAgent(),
        CardiologyAgent(),
        NeurologyAgent(),
        PulmonologyAgent(),
        ToxicologyAgent(),
    ]
    for agent in agents:
        d = agent.describe()
        assert "name" in d, f"{type(agent).__name__} missing 'name'"
        assert "domain" in d, f"{type(agent).__name__} missing 'domain'"
        assert "model" in d, f"{type(agent).__name__} missing 'model'"
        assert d["name"], f"{type(agent).__name__} has empty name"
        assert d["model"], f"{type(agent).__name__} has empty model"


def test_describe_returns_correct_values():
    expected = {
        IntakeAgent: ("intake", "intake", "qwen2.5:7b"),
        ImageAnalysisAgent: ("image-analysis", "imaging", "medgemma:27b"),
        CardiologyAgent: ("cardiology", "cardiology", "cardiology"),
        NeurologyAgent: ("neurology", "neurology", "neurology"),
        PulmonologyAgent: ("pulmonology", "pulmonology", "pulmonology"),
        ToxicologyAgent: ("toxicology", "toxicology", "toxicology"),
    }
    for AgentClass, (name, domain, model) in expected.items():
        agent = AgentClass()
        d = agent.describe()
        assert d["name"] == name
        assert d["domain"] == domain
        assert d["model"] == model


# ── inference_url routing ─────────────────────────────────────────────────────


def test_specialist_agents_use_vllm():
    for AgentClass in [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent]:
        assert AgentClass.inference_url == settings.VLLM_BASE_URL, (
            f"{AgentClass.__name__} should use VLLM_BASE_URL"
        )


def test_ollama_agents_use_ollama():
    for AgentClass in [IntakeAgent, ImageAnalysisAgent]:
        assert AgentClass.inference_url == settings.OLLAMA_BASE_URL, (
            f"{AgentClass.__name__} should use OLLAMA_BASE_URL"
        )


# ── IntakeAgent ───────────────────────────────────────────────────────────────


async def test_intake_returns_specialist_result():
    result = await IntakeAgent().run(fresh_case())
    assert isinstance(result, SpecialistResult)
    assert result.domain == "intake"
    assert result.agent_name == "intake"


async def test_intake_populates_conditions():
    case = fresh_case()
    await IntakeAgent().run(case)
    assert len(case.conditions) > 0
    for c in case.conditions:
        assert c.system
        assert c.code
        assert c.display


async def test_intake_populates_observations():
    case = fresh_case()
    await IntakeAgent().run(case)
    assert len(case.observations) > 0
    for o in case.observations:
        assert o.loinc_code
        assert o.display


async def test_intake_populates_medications():
    case = fresh_case()
    await IntakeAgent().run(case)
    assert len(case.medications) > 0
    for m in case.medications:
        assert m.rxnorm_code
        assert m.name


async def test_intake_custom_mock_empty_payload():
    empty = json.dumps({"conditions": [], "observations": [], "medications": []})
    with patch("agents.intake.intake_agent.call_chat", AsyncMock(return_value=empty)):
        case = fresh_case()
        result = await IntakeAgent().run(case)
        assert result.domain == "intake"
        assert case.conditions == []
        assert case.observations == []
        assert case.medications == []


async def test_intake_custom_mock_missing_keys():
    """Partial JSON (missing observations/medications) should not raise."""
    partial = json.dumps(
        {
            "conditions": [
                {"system": "http://snomed.info/sct", "code": "73211009", "display": "DM2"}
            ]
        }
    )
    with patch("agents.intake.intake_agent.call_chat", AsyncMock(return_value=partial)):
        case = fresh_case()
        result = await IntakeAgent().run(case)
        assert len(case.conditions) == 1
        assert case.observations == []
        assert case.medications == []


# ── ImageAnalysisAgent ────────────────────────────────────────────────────────


async def test_image_agent_no_attachments_returns_empty():
    case = fresh_case()
    assert case.imaging_attachments == []
    result = await ImageAnalysisAgent().run(case)
    assert isinstance(result, SpecialistResult)
    assert result.domain == "imaging"
    assert result.diagnoses == []


async def test_image_agent_with_attachments_returns_diagnoses():
    case = fresh_case(imaging_attachments=["https://example.com/cxr.jpg"])
    result = await ImageAnalysisAgent().run(case)
    assert result.domain == "imaging"
    assert len(result.diagnoses) > 0


async def test_image_agent_early_exit_skips_llm():
    """Confirm the LLM is never called when there are no attachments."""
    with patch("agents.specialists.image_agent.call_chat", AsyncMock()) as mock_llm:
        await ImageAnalysisAgent().run(fresh_case())
        mock_llm.assert_not_called()


# ── Specialist agents ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "AgentClass,expected_domain",
    [
        (CardiologyAgent, "cardiology"),
        (NeurologyAgent, "neurology"),
        (PulmonologyAgent, "pulmonology"),
        (ToxicologyAgent, "toxicology"),
    ],
)
async def test_specialist_returns_correct_domain(AgentClass, expected_domain):
    result = await AgentClass().run(fresh_case())
    assert isinstance(result, SpecialistResult)
    assert result.domain == expected_domain
    assert result.agent_name == expected_domain


@pytest.mark.parametrize(
    "AgentClass",
    [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent],
)
async def test_specialist_confidence_sums_le_1(AgentClass):
    result = await AgentClass().run(fresh_case())
    total = sum(d.confidence for d in result.diagnoses)
    assert total <= 1.0 + 1e-6, (
        f"{AgentClass.__name__} confidence sum {total:.4f} exceeds 1.0"
    )


@pytest.mark.parametrize(
    "AgentClass",
    [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent],
)
async def test_specialist_diagnoses_ranked(AgentClass):
    result = await AgentClass().run(fresh_case())
    ranks = [d.rank for d in result.diagnoses]
    assert ranks == sorted(ranks), f"{AgentClass.__name__} diagnoses not in rank order"


@pytest.mark.parametrize(
    "AgentClass",
    [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent],
)
async def test_specialist_has_reasoning_trace(AgentClass):
    result = await AgentClass().run(fresh_case())
    assert isinstance(result.reasoning_trace, str)
    assert len(result.reasoning_trace) > 0


@pytest.mark.parametrize(
    "AgentClass",
    [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent],
)
async def test_specialist_custom_mock(AgentClass):
    """Custom payload: verify parsing still works with user-supplied JSON."""
    custom = json.dumps(
        {
            "diagnoses": [
                {
                    "rank": 1,
                    "display": "Test diagnosis",
                    "confidence": 0.9,
                    "snomed_code": "123456789",
                    "flags": ["TEST"],
                }
            ],
            "reasoning_trace": "Custom mock trace.",
        }
    )
    module = AgentClass.__module__
    with patch(f"{module}.call_chat", AsyncMock(return_value=custom)):
        result = await AgentClass().run(fresh_case())
        assert len(result.diagnoses) == 1
        assert result.diagnoses[0].display == "Test diagnosis"
        assert result.diagnoses[0].confidence == pytest.approx(0.9)
        assert result.reasoning_trace == "Custom mock trace."


# ── case_id propagation ───────────────────────────────────────────────────────


async def test_result_case_id_matches_input():
    case = fresh_case()
    for AgentClass in [
        IntakeAgent, ImageAnalysisAgent,
        CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent,
    ]:
        result = await AgentClass().run(case)
        assert result.case_id == case.case_id, (
            f"{AgentClass.__name__} returned wrong case_id"
        )
