"""Triage → FHIR bundle builder and LOINC narrative mapping (issue #70)."""

from __future__ import annotations

import pytest

from shadi_fhir.normalizer import FHIRNormalizer
from shadi_fhir.triage_bundle import build_triage_bundle


def test_build_triage_bundle_requires_text() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        build_triage_bundle(
            patient_id="p1",
            encounter_id="e1",
            triage_text="   ",
        )


def test_bundle_to_case_triage_narrative() -> None:
    bundle = build_triage_bundle(
        patient_id="p-demo",
        encounter_id="e-demo",
        triage_text="Chest pain x2h, radiates to L arm. Vitals stable.",
        chief_complaint="Chest pain",
    )
    case = FHIRNormalizer().bundle_to_case(bundle)
    assert case.patient_id == "p-demo"
    assert case.encounter_id == "e-demo"
    assert case.chief_complaint == "Chest pain"
    assert "Chest pain x2h" in case.triage_notes_raw
    assert case.observations == []


def test_triage_loinc_not_in_clinical_observations_list() -> None:
    """Triage LOINC observation must not appear in ``observations`` list."""
    bundle = build_triage_bundle(
        patient_id="p1",
        encounter_id="e1",
        triage_text="Sob x1 day",
    )
    case = FHIRNormalizer().bundle_to_case(bundle)
    assert case.observations == []
    assert "Sob" in case.triage_notes_raw
