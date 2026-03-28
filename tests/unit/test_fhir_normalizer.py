"""Tests for FHIR R4 bundle normalization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.schemas import CaseObject
from shadi_fhir.exceptions import FHIRValidationError
from shadi_fhir.normalizer import FHIRNormalizer

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample_bundle.json"


def _load_bundle() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_bundle_to_case_happy_path() -> None:
    bundle = _load_bundle()
    case = FHIRNormalizer().bundle_to_case(bundle)
    assert case.patient_id == "pat-sample-1"
    assert case.encounter_id == "enc-sample-1"
    assert case.chief_complaint == "Shortness of breath"
    assert case.triage_notes_raw == ""
    assert case.age is not None and case.age >= 30
    assert case.sex == "male"
    assert len(case.conditions) == 1
    assert case.conditions[0].code == "267036007"
    assert len(case.observations) == 1
    assert case.observations[0].loinc_code == "8867-4"
    assert len(case.medications) == 1
    assert "Acetaminophen" in case.medications[0].name
    assert len(case.allergies) == 1
    assert case.allergies[0].substance == "Penicillin"


def test_case_object_from_fhir_bundle() -> None:
    bundle = _load_bundle()
    case = CaseObject.from_fhir_bundle(bundle)
    assert isinstance(case, CaseObject)
    assert case.encounter_id == "enc-sample-1"


def test_bundle_missing_patient_raises() -> None:
    bundle = _load_bundle()
    bundle["entry"] = [e for e in bundle["entry"] if e["resource"]["resourceType"] != "Patient"]
    with pytest.raises(FHIRValidationError, match="Patient"):
        FHIRNormalizer().bundle_to_case(bundle)


def test_bundle_missing_encounter_raises() -> None:
    bundle = _load_bundle()
    bundle["entry"] = [e for e in bundle["entry"] if e["resource"]["resourceType"] != "Encounter"]
    with pytest.raises(FHIRValidationError, match="Encounter"):
        FHIRNormalizer().bundle_to_case(bundle)


def test_optional_resources_only_patient_encounter() -> None:
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1", "gender": "female"}},
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "e1",
                    "status": "arrived",
                    "subject": {"reference": "Patient/p1"},
                }
            },
        ],
    }
    case = FHIRNormalizer().bundle_to_case(bundle)
    assert case.conditions == []
    assert case.observations == []
    assert case.medications == []
    assert case.allergies == []
    assert case.chief_complaint == ""
