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


def test_build_triage_bundle_requires_patient_and_encounter_ids() -> None:
    with pytest.raises(ValueError, match="patient_id"):
        build_triage_bundle(patient_id="  ", encounter_id="e1", triage_text="ok")
    with pytest.raises(ValueError, match="encounter_id"):
        build_triage_bundle(patient_id="p1", encounter_id="", triage_text="ok")


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


def test_non_loinc_system_same_code_not_treated_as_triage_narrative() -> None:
    """Code 34109-9 without LOINC system must not populate ``triage_notes_raw``."""
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1"}},
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "e1",
                    "status": "arrived",
                    "subject": {"reference": "Patient/p1"},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {
                        "coding": [
                            {"system": "http://acme.test/fhir", "code": "34109-9", "display": "fake"}
                        ]
                    },
                    "subject": {"reference": "Patient/p1"},
                    "valueString": "should not be triage",
                }
            },
        ],
    }
    case = FHIRNormalizer().bundle_to_case(bundle)
    assert case.triage_notes_raw == ""


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
