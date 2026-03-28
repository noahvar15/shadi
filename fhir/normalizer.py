"""FHIR R4 resource normalizer.

Converts raw FHIR resources (Patient, Observation, Condition,
MedicationRequest, AllergyIntolerance) into the internal CaseObject schema.
"""

from __future__ import annotations

import structlog
from fhir.resources.allergyintolerance import AllergyIntolerance
from fhir.resources.condition import Condition
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.observation import Observation as FHIRObservation
from fhir.resources.patient import Patient

from agents.schemas import Allergy, ClinicalCode, CaseObject, Medication, Observation

logger = structlog.get_logger()


class FHIRNormalizer:
    """Converts FHIR resource bundles into CaseObject instances."""

    def normalize_condition(self, resource: Condition) -> ClinicalCode | None:
        if not resource.code or not resource.code.coding:
            return None
        coding = resource.code.coding[0]
        return ClinicalCode(
            system=coding.system or "",
            code=coding.code or "",
            display=coding.display or resource.code.text or "",
        )

    def normalize_observation(self, resource: FHIRObservation) -> Observation | None:
        if not resource.code or not resource.code.coding:
            return None
        coding = resource.code.coding[0]
        value: str | float | None = None
        unit: str | None = None
        if resource.valueQuantity:
            value = resource.valueQuantity.value
            unit = resource.valueQuantity.unit
        elif resource.valueString:
            value = resource.valueString
        return Observation(
            loinc_code=coding.code or "",
            display=coding.display or "",
            value=value,
            unit=unit,
        )

    def normalize_medication(self, resource: MedicationRequest) -> Medication | None:
        if not resource.medicationCodeableConcept:
            return None
        codings = resource.medicationCodeableConcept.coding or []
        rxnorm = next((c.code for c in codings if "rxnorm" in (c.system or "").lower()), "")
        name = resource.medicationCodeableConcept.text or ""
        return Medication(rxnorm_code=rxnorm or "", name=name)

    def normalize_allergy(self, resource: AllergyIntolerance) -> Allergy | None:
        if not resource.code:
            return None
        codings = resource.code.coding or []
        rxnorm = next((c.code for c in codings if "rxnorm" in (c.system or "").lower()), None)
        substance = resource.code.text or ""
        reaction: str | None = None
        severity: str | None = None
        if resource.reaction:
            r = resource.reaction[0]
            if r.manifestation:
                reaction = r.manifestation[0].text
            if r.severity:
                severity = r.severity
        return Allergy(
            substance=substance,
            rxnorm_code=rxnorm,
            reaction=reaction,
            severity=severity,
        )
