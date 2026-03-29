"""Integration test for the full Orchestrator pipeline under MOCK_LLM=true."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("MOCK_LLM", "true")

from agents.orchestrator.orchestrator import Orchestrator
from agents.schemas import CaseObject


@pytest.fixture
def sample_case() -> CaseObject:
    return CaseObject(
        patient_id="PT-TEST-001",
        encounter_id="ENC-TEST-001",
        chief_complaint="Chest pain radiating to left arm, diaphoretic",
        triage_notes_raw=(
            "62yo male presenting with acute onset chest pain 2h ago. "
            "Pain radiates to left arm and jaw. Diaphoretic. "
            "BP 145/92, HR 102, RR 18, O2 97%."
        ),
        age=62,
        sex="male",
    )


@pytest.mark.asyncio
async def test_full_pipeline_completes(sample_case: CaseObject):
    """Run the full orchestrator and verify the report is structurally valid."""
    orchestrator = Orchestrator()

    steps_seen: list[str] = []

    async def track_step(name: str) -> None:
        steps_seen.append(name)

    report = await orchestrator.run(sample_case, on_step=track_step)

    assert report.case_id == sample_case.case_id
    assert isinstance(report.top_diagnoses, list)
    assert isinstance(report.consensus_level, float)
    assert 0.0 <= report.consensus_level <= 1.0
    assert isinstance(report.divergent_agents, list)
    assert isinstance(report.vetoed_recommendations, list)

    expected_steps = ["intake", "imaging", "specialists", "evidence", "debate", "synthesis", "safety"]
    assert steps_seen == expected_steps


@pytest.mark.asyncio
async def test_pipeline_without_on_step(sample_case: CaseObject):
    """Pipeline runs without on_step callback."""
    orchestrator = Orchestrator()
    report = await orchestrator.run(sample_case)
    assert report.case_id == sample_case.case_id
