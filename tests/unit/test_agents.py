"""Unit tests for all six agent classes.

All tests run against mock LLM responses (MOCK_LLM=True is the default in
config.py). No models need to be downloaded; no inference servers need to be
running.

Coverage:
  - Async tests use ``@pytest.mark.asyncio`` explicitly (in addition to
    ``asyncio_mode = auto`` in ``pyproject.toml``).
  - BaseAgent.describe() contract for all six agents
  - inference_url routing: Ollama for intake, image, specialists, evidence
  - IntakeAgent.run() populates case.conditions / observations / medications
  - ImageAnalysisAgent early-exit when imaging_attachments is empty
  - ImageAnalysisAgent returns diagnoses when attachments are present
  - All specialist agents return SpecialistResult with domain set correctly
  - DiagnosisCandidate confidence values sum ≤ 1.0 for every specialist
  - Custom mock: overriding call_chat to test specific payloads
  - Custom mock: handling of partial/missing JSON keys
  - EvidenceAgent mock-mode short-circuit (no DB, no crash)
  - EvidenceAgent attaches EvidenceCitation when claim eval returns SUPPORTS
  - EvidenceAgent skips citation when claim eval returns REFUTES
  - EvidenceAgent graceful degradation when pgvector returns no rows
  - EvidenceAgent inference_url routes to Ollama
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agents.evidence.evidence_agent import EvidenceAgent
from agents.intake.intake_agent import IntakeAgent
from agents.safety.veto_agent import SafetyVetoAgent
from agents.schemas import (
    Allergy,
    CaseObject,
    DiagnosisCandidate,
    DifferentialReport,
    EvidenceResult,
    SafetyResult,
    SpecialistResult,
    VetoDecision,
)
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
        ImageAnalysisAgent: ("image-analysis", "imaging", "alibayram/medgemma:27b"),
        CardiologyAgent: ("cardiology", "cardiology", settings.MEDITRON_MODEL),
        NeurologyAgent: ("neurology", "neurology", settings.MEDITRON_MODEL),
        PulmonologyAgent: ("pulmonology", "pulmonology", settings.MEDITRON_MODEL),
        ToxicologyAgent: ("toxicology", "toxicology", settings.MEDITRON_MODEL),
    }
    for AgentClass, (name, domain, model) in expected.items():
        agent = AgentClass()
        d = agent.describe()
        assert d["name"] == name
        assert d["domain"] == domain
        assert d["model"] == model


# ── inference_url routing ─────────────────────────────────────────────────────


def test_specialist_agents_use_ollama_meditron():
    for AgentClass in [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent]:
        assert AgentClass.inference_url == settings.OLLAMA_BASE_URL, (
            f"{AgentClass.__name__} should use OLLAMA_BASE_URL"
        )


def test_ollama_agents_use_ollama():
    for AgentClass in [IntakeAgent, ImageAnalysisAgent]:
        assert AgentClass.inference_url == settings.OLLAMA_BASE_URL, (
            f"{AgentClass.__name__} should use OLLAMA_BASE_URL"
        )


# ── IntakeAgent ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_intake_returns_specialist_result():
    result = await IntakeAgent().run(fresh_case())
    assert isinstance(result, SpecialistResult)
    assert result.domain == "intake"
    assert result.agent_name == "intake"


@pytest.mark.asyncio
async def test_intake_populates_conditions():
    case = fresh_case()
    await IntakeAgent().run(case)
    assert len(case.conditions) > 0
    for c in case.conditions:
        assert c.system
        assert c.code
        assert c.display


@pytest.mark.asyncio
async def test_intake_populates_observations():
    case = fresh_case()
    await IntakeAgent().run(case)
    assert len(case.observations) > 0
    for o in case.observations:
        assert o.loinc_code
        assert o.display


@pytest.mark.asyncio
async def test_intake_populates_medications():
    case = fresh_case()
    await IntakeAgent().run(case)
    assert len(case.medications) > 0
    for m in case.medications:
        assert m.rxnorm_code
        assert m.name


@pytest.mark.asyncio
async def test_intake_custom_mock_empty_payload():
    empty = json.dumps({"conditions": [], "observations": [], "medications": []})
    with patch("agents.intake.intake_agent.call_chat", AsyncMock(return_value=empty)):
        case = fresh_case()
        result = await IntakeAgent().run(case)
        assert result.domain == "intake"
        assert case.conditions == []
        assert case.observations == []
        assert case.medications == []


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_image_agent_no_attachments_returns_empty():
    case = fresh_case()
    assert case.imaging_attachments == []
    result = await ImageAnalysisAgent().run(case)
    assert isinstance(result, SpecialistResult)
    assert result.domain == "imaging"
    assert result.diagnoses == []


@pytest.mark.asyncio
async def test_image_agent_with_attachments_returns_diagnoses():
    case = fresh_case(imaging_attachments=["https://example.com/cxr.jpg"])
    result = await ImageAnalysisAgent().run(case)
    assert result.domain == "imaging"
    assert len(result.diagnoses) > 0


@pytest.mark.asyncio
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
@pytest.mark.asyncio
async def test_specialist_returns_correct_domain(AgentClass, expected_domain):
    result = await AgentClass().run(fresh_case())
    assert isinstance(result, SpecialistResult)
    assert result.domain == expected_domain
    assert result.agent_name == expected_domain


@pytest.mark.parametrize(
    "AgentClass",
    [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent],
)
@pytest.mark.asyncio
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
@pytest.mark.asyncio
async def test_specialist_diagnoses_ranked(AgentClass):
    result = await AgentClass().run(fresh_case())
    ranks = [d.rank for d in result.diagnoses]
    assert ranks == sorted(ranks), f"{AgentClass.__name__} diagnoses not in rank order"


@pytest.mark.parametrize(
    "AgentClass",
    [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent],
)
@pytest.mark.asyncio
async def test_specialist_has_reasoning_trace(AgentClass):
    result = await AgentClass().run(fresh_case())
    assert isinstance(result.reasoning_trace, str)
    assert len(result.reasoning_trace) > 0


@pytest.mark.parametrize(
    "AgentClass",
    [CardiologyAgent, NeurologyAgent, PulmonologyAgent, ToxicologyAgent],
)
@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


# ── EvidenceAgent ─────────────────────────────────────────────────────────────

def fresh_specialist_result() -> SpecialistResult:
    """Return a deep-copied cardiology SpecialistResult for evidence tests.

    Must be called fresh per test so mutations to DiagnosisCandidate.supporting_evidence
    in one test do not bleed into the next.
    """
    return SpecialistResult(
        agent_name="cardiology",
        case_id=MOCK_CASE.case_id,
        domain="cardiology",
        diagnoses=[
            DiagnosisCandidate(
                rank=1,
                display="Acute myocardial infarction",
                confidence=0.75,
                snomed_code="57054005",
            )
        ],
        reasoning_trace="Test trace.",
    )


# Module-level alias for tests that don't mutate the diagnoses list.
_EVIDENCE_SPECIALIST_RESULT = fresh_specialist_result()


def test_evidence_agent_describe():
    d = EvidenceAgent().describe()
    assert d["name"] == "evidence"
    assert d["domain"] == "evidence"
    assert d["model"] == settings.EVIDENCE_EMBED_MODEL


def test_evidence_agent_uses_ollama():
    assert EvidenceAgent.inference_url == settings.OLLAMA_BASE_URL


@pytest.mark.asyncio
async def test_evidence_agent_mock_mode_no_crash():
    """MOCK_LLM=True (default): run completes without touching DB or Ollama."""
    case = fresh_case()
    result = await EvidenceAgent().run(case, [_EVIDENCE_SPECIALIST_RESULT])
    assert isinstance(result, EvidenceResult)
    assert result.agent_name == "evidence"
    assert result.case_id == case.case_id


@pytest.mark.asyncio
async def test_evidence_agent_mock_mode_returns_diagnoses_unchanged():
    """In mock mode, grounded_diagnoses contains the input candidates unmodified."""
    case = fresh_case()
    result = await EvidenceAgent().run(case, [_EVIDENCE_SPECIALIST_RESULT])
    assert len(result.grounded_diagnoses) == 1
    assert result.grounded_diagnoses[0].display == "Acute myocardial infarction"
    assert result.grounded_diagnoses[0].supporting_evidence == []


@pytest.mark.asyncio
async def test_evidence_agent_mock_mode_skips_embed():
    """Confirm the Ollama /api/embeddings endpoint is never called in mock mode."""
    case = fresh_case()
    with patch("agents.evidence.evidence_agent.httpx.AsyncClient") as mock_client:
        await EvidenceAgent().run(case, [_EVIDENCE_SPECIALIST_RESULT])
        mock_client.assert_not_called()


def _make_real_mode_patches(mock_conn: MagicMock, mock_http_resp_embedding: list[float]):
    """Return context-manager patches shared by real-mode evidence tests.

    asyncpg is imported lazily inside EvidenceAgent.reason, so we patch it via
    the ``sys.modules`` shim rather than a module-level attribute.
    """
    import sys
    import types

    asyncpg_stub = types.ModuleType("asyncpg")
    asyncpg_stub.connect = AsyncMock(return_value=mock_conn)  # type: ignore[attr-defined]
    sys.modules.setdefault("asyncpg", asyncpg_stub)
    # Override connect regardless of whether asyncpg was already in sys.modules.
    sys.modules["asyncpg"].connect = AsyncMock(return_value=mock_conn)  # type: ignore[attr-defined]

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"embedding": mock_http_resp_embedding}
    mock_resp.raise_for_status = MagicMock()
    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(
        return_value=MagicMock(post=AsyncMock(return_value=mock_resp))
    )
    mock_http.__aexit__ = AsyncMock(return_value=False)

    return mock_http


@pytest.mark.asyncio
async def test_evidence_agent_empty_pgvector_no_crash():
    """Real-mode: empty pgvector table → no citations, no exception."""
    case = fresh_case()

    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.close = AsyncMock()
    mock_http = _make_real_mode_patches(mock_conn, [0.1] * 768)

    with (
        patch("agents.evidence.evidence_agent.settings") as mock_settings,
        patch("agents.evidence.evidence_agent.httpx.AsyncClient", return_value=mock_http),
    ):
        mock_settings.MOCK_LLM = False
        mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
        mock_settings.MEDITRON_MODEL = settings.MEDITRON_MODEL
        mock_settings.DATABASE_URL = "postgresql+asyncpg://shadi:shadi@localhost:5432/shadi"

        result = await EvidenceAgent().run(case, [_EVIDENCE_SPECIALIST_RESULT])

    assert isinstance(result, EvidenceResult)
    assert result.grounded_diagnoses[0].supporting_evidence == []


@pytest.mark.asyncio
async def test_evidence_agent_supports_attaches_citation():
    """Real-mode: SUPPORTS verdict → EvidenceCitation is appended."""
    case = fresh_case()

    mock_row = {"excerpt": "AMI is the leading cause...", "source": "PubMed:12345678", "distance": 0.25}
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[mock_row])
    mock_conn.close = AsyncMock()
    mock_http = _make_real_mode_patches(mock_conn, [0.1] * 768)

    supports_payload = json.dumps({"verdict": "SUPPORTS", "explanation": "Directly relevant."})

    with (
        patch("agents.evidence.evidence_agent.settings") as mock_settings,
        patch("agents.evidence.evidence_agent.httpx.AsyncClient", return_value=mock_http),
        patch("agents.evidence.evidence_agent.call_chat", AsyncMock(return_value=supports_payload)),
    ):
        mock_settings.MOCK_LLM = False
        mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
        mock_settings.MEDITRON_MODEL = settings.MEDITRON_MODEL
        mock_settings.DATABASE_URL = "postgresql+asyncpg://shadi:shadi@localhost:5432/shadi"

        result = await EvidenceAgent().run(case, [fresh_specialist_result()])

    citations = result.grounded_diagnoses[0].supporting_evidence
    assert len(citations) == 1
    assert citations[0].source == "PubMed:12345678"
    assert citations[0].excerpt == "AMI is the leading cause..."
    # relevance_score should be 1.0 - cosine_distance (0.25) = 0.75
    assert citations[0].relevance_score == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_evidence_agent_refutes_no_citation():
    """Real-mode: REFUTES verdict → no EvidenceCitation is attached."""
    case = fresh_case()

    mock_row = {"excerpt": "Unrelated passage.", "source": "PubMed:99999999", "distance": 0.38}
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[mock_row])
    mock_conn.close = AsyncMock()
    mock_http = _make_real_mode_patches(mock_conn, [0.1] * 768)

    refutes_payload = json.dumps({"verdict": "REFUTES", "explanation": "Contradicts AMI."})

    with (
        patch("agents.evidence.evidence_agent.settings") as mock_settings,
        patch("agents.evidence.evidence_agent.httpx.AsyncClient", return_value=mock_http),
        patch("agents.evidence.evidence_agent.call_chat", AsyncMock(return_value=refutes_payload)),
    ):
        mock_settings.MOCK_LLM = False
        mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
        mock_settings.MEDITRON_MODEL = settings.MEDITRON_MODEL
        mock_settings.DATABASE_URL = "postgresql+asyncpg://shadi:shadi@localhost:5432/shadi"

        result = await EvidenceAgent().run(case, [fresh_specialist_result()])

    assert result.grounded_diagnoses[0].supporting_evidence == []


@pytest.mark.asyncio
async def test_evidence_agent_result_case_id_matches_input():
    case = fresh_case()
    result = await EvidenceAgent().run(case, [_EVIDENCE_SPECIALIST_RESULT])
    assert result.case_id == case.case_id


@pytest.mark.asyncio
async def test_evidence_agent_multiple_specialist_results():
    """All diagnoses from multiple specialist results are collected."""
    case = fresh_case()
    neuro_result = SpecialistResult(
        agent_name="neurology",
        case_id=case.case_id,
        domain="neurology",
        diagnoses=[
            DiagnosisCandidate(rank=1, display="Cerebrovascular accident", confidence=0.55)
        ],
        reasoning_trace="",
    )
    result = await EvidenceAgent().run(case, [_EVIDENCE_SPECIALIST_RESULT, neuro_result])
    assert len(result.grounded_diagnoses) == 2


# ── SafetyVetoAgent ───────────────────────────────────────────────────────────


def _make_report(*next_steps_lists: list[str]) -> "DifferentialReport":
    """Build a minimal DifferentialReport with the given per-diagnosis next_steps."""
    diagnoses = [
        DiagnosisCandidate(rank=i + 1, display=f"Diagnosis {i + 1}", confidence=0.5, next_steps=steps)
        for i, steps in enumerate(next_steps_lists)
    ]
    return DifferentialReport(case_id=MOCK_CASE.case_id, top_diagnoses=diagnoses)


def test_safety_veto_describe():
    d = SafetyVetoAgent().describe()
    assert d["name"] == "safety-veto"
    assert d["domain"] == "safety"
    assert d["model"] == settings.SAFETY_MODEL


def test_safety_veto_uses_ollama():
    assert SafetyVetoAgent.inference_url == settings.OLLAMA_BASE_URL


async def test_safety_veto_mock_mode_no_crash():
    """MOCK_LLM=True (default): run completes without touching Ollama."""
    case = fresh_case()
    report = _make_report(["Order ECG", "Check troponin"])
    result = await SafetyVetoAgent().run(case, report)
    assert isinstance(result, SafetyResult)
    assert result.agent_name == "safety-veto"
    assert result.case_id == case.case_id


async def test_safety_veto_mock_mode_all_not_vetoed():
    """In mock mode, all decisions are vetoed=False."""
    case = fresh_case()
    report = _make_report(["Order ECG", "Check troponin"])
    result = await SafetyVetoAgent().run(case, report)
    assert all(not d.vetoed for d in result.decisions)


async def test_safety_veto_one_decision_per_next_step():
    """One VetoDecision is returned per next_steps item across all diagnoses."""
    case = fresh_case()
    report = _make_report(["Step A", "Step B"], ["Step C"])

    payload = json.dumps({
        "decisions": [
            {"recommendation": "Step A", "vetoed": False, "reason": None, "contraindication_codes": []},
            {"recommendation": "Step B", "vetoed": False, "reason": None, "contraindication_codes": []},
            {"recommendation": "Step C", "vetoed": False, "reason": None, "contraindication_codes": []},
        ]
    })
    with patch("agents.safety.veto_agent.call_chat", AsyncMock(return_value=payload)):
        with patch("agents.safety.veto_agent.settings") as mock_settings:
            mock_settings.MOCK_LLM = False
            mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
            result = await SafetyVetoAgent().run(case, report)

    assert len(result.decisions) == 3
    assert result.decisions[0].recommendation == "Step A"
    assert result.decisions[1].recommendation == "Step B"
    assert result.decisions[2].recommendation == "Step C"


async def test_safety_veto_penicillin_allergy_amoxicillin_vetoed():
    """Amoxicillin recommendation is vetoed for a penicillin-allergic patient."""
    case = fresh_case(
        allergies=[Allergy(substance="Penicillin", rxnorm_code="7980", reaction="Anaphylaxis", severity="severe")],
    )
    report = _make_report(["Administer amoxicillin 500 mg PO TID"])

    payload = json.dumps({
        "decisions": [
            {
                "recommendation": "Administer amoxicillin 500 mg PO TID",
                "vetoed": True,
                "reason": "Amoxicillin is a penicillin-class antibiotic; contraindicated given documented severe penicillin allergy (anaphylaxis).",
                "contraindication_codes": ["723"],
            }
        ]
    })
    with patch("agents.safety.veto_agent.call_chat", AsyncMock(return_value=payload)):
        with patch("agents.safety.veto_agent.settings") as mock_settings:
            mock_settings.MOCK_LLM = False
            mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
            result = await SafetyVetoAgent().run(case, report)

    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision.vetoed is True
    assert decision.reason is not None
    assert "723" in decision.contraindication_codes
    assert any(result.decisions[i].vetoed for i in range(len(result.decisions)))


async def test_safety_veto_clean_report_all_not_vetoed():
    """A report with no contraindications returns vetoed=False on all decisions."""
    case = fresh_case()
    report = _make_report(["Order chest X-ray", "Draw CBC with differential"])

    payload = json.dumps({
        "decisions": [
            {"recommendation": "Order chest X-ray", "vetoed": False, "reason": None, "contraindication_codes": []},
            {"recommendation": "Draw CBC with differential", "vetoed": False, "reason": None, "contraindication_codes": []},
        ]
    })
    with patch("agents.safety.veto_agent.call_chat", AsyncMock(return_value=payload)):
        with patch("agents.safety.veto_agent.settings") as mock_settings:
            mock_settings.MOCK_LLM = False
            mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
            result = await SafetyVetoAgent().run(case, report)

    assert not any(d.vetoed for d in result.decisions)


async def test_safety_veto_parse_error_fallback():
    """Malformed LLM response sets parse_error=True and vetoes all decisions (fail-closed)."""
    case = fresh_case()
    report = _make_report(["Order ECG"])

    with patch("agents.safety.veto_agent.call_chat", AsyncMock(return_value="not valid json {")):
        with patch("agents.safety.veto_agent.settings") as mock_settings:
            mock_settings.MOCK_LLM = False
            mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
            result = await SafetyVetoAgent().run(case, report)

    assert len(result.decisions) == 1
    assert result.decisions[0].vetoed is True
    assert result.parse_error is True


async def test_safety_veto_partial_response_is_fail_closed():
    """LLM returning fewer decisions than recommendations triggers parse_error and vetoes all."""
    case = fresh_case()
    report = _make_report(["Order ECG", "Draw troponin", "CT-PA to rule out PE"])

    # phi4 returns only 1 decision for 3 recommendations
    partial_payload = json.dumps({
        "decisions": [
            {"recommendation": "Order ECG", "vetoed": False, "reason": None, "contraindication_codes": []},
        ]
    })
    with patch("agents.safety.veto_agent.call_chat", AsyncMock(return_value=partial_payload)):
        with patch("agents.safety.veto_agent.settings") as mock_settings:
            mock_settings.MOCK_LLM = False
            mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
            result = await SafetyVetoAgent().run(case, report)

    assert result.parse_error is True
    assert len(result.decisions) == 3
    assert all(d.vetoed for d in result.decisions)


async def test_safety_veto_empty_report_returns_empty_decisions():
    """A report with no diagnoses (no next_steps) returns an empty decisions list."""
    case = fresh_case()
    report = DifferentialReport(case_id=case.case_id, top_diagnoses=[])

    with patch("agents.safety.veto_agent.settings") as mock_settings:
        mock_settings.MOCK_LLM = False
        mock_settings.OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
        result = await SafetyVetoAgent().run(case, report)

    assert result.decisions == []


async def test_safety_veto_result_case_id_matches_input():
    case = fresh_case()
    report = _make_report(["Order ECG"])
    result = await SafetyVetoAgent().run(case, report)
    assert result.case_id == case.case_id
