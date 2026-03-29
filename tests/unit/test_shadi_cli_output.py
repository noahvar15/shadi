"""End-to-end Shadi pipeline smoke test with CLI-formatted output (MOCK_LLM)."""

from __future__ import annotations

import pytest

from agents.cli_output import format_shadi_cli_report
from agents.orchestrator.orchestrator import Orchestrator
from agents.schemas import CaseObject, DiagnosisCandidate, DifferentialReport


def test_format_shadi_cli_report_structure() -> None:
    case = CaseObject(
        patient_id="p1",
        encounter_id="e1",
        chief_complaint="Fever",
        triage_notes_raw="T 39C, productive cough x3d.",
    )
    report = DifferentialReport(
        case_id=case.case_id,
        top_diagnoses=[
            DiagnosisCandidate(
                rank=1,
                display="Community-acquired pneumonia",
                confidence=0.7,
                snomed_code="385093006",
                next_steps=["CXR", "blood cultures"],
                flags=["MOCK"],
            )
        ],
        consensus_level=0.5,
        divergent_agents=["cardiology"],
        vetoed_recommendations=[],
    )
    text = format_shadi_cli_report(case, report)
    assert "SHADI — multi-agent differential" in text
    assert str(case.case_id) in text
    assert "Community-acquired pneumonia" in text
    assert "confidence: 0.70" in text
    assert "Consensus level" in text
    assert "cardiology" in text
    assert "No recommendations vetoed" in text


@pytest.mark.asyncio
async def test_shadi_multi_agent_pipeline_cli_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Full orchestrator run under MOCK_LLM; prints CLI report (use ``pytest -s`` to view)."""
    case = CaseObject(
        patient_id="pytest-cli-patient",
        encounter_id="pytest-cli-encounter",
        chief_complaint="Chest pain",
        triage_notes_raw="Substernal pressure; rule out ACS.",
    )

    report = await Orchestrator().run(case)
    text = format_shadi_cli_report(case, report)

    print(text)
    out = capsys.readouterr().out

    assert "SHADI — multi-agent differential" in text
    assert "Acute myocardial infarction (mock)" in text
    assert "Pulmonary embolism (mock)" in text
    assert "Consensus level" in text
    assert "Safety veto" in text
    assert "No recommendations vetoed" in text
    assert str(case.case_id) in text

    assert text in out
    assert out.endswith("\n")
