"""FHIR R4 resource normalizer.

Converts raw FHIR resources (Patient, Observation, Condition,
MedicationRequest, AllergyIntolerance) into the internal CaseObject schema.

Incoming bundles are expected as **FHIR R4** JSON (Epic/Cerner). Private helpers
(``_clinical_code_from_codeable_*``, ``_build_observation``, etc.) implement
the mapping once; :meth:`FHIRNormalizer.normalize_*` delegates to those same
helpers so dict-based :meth:`bundle_to_case` and programmatic ``fhir.resources``
call sites cannot drift. The ``fhir.resources`` types may target a newer FHIR
version than R4 JSON from the EHR — R4 dict parsing remains the source path
for bundles.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, cast

import structlog
from fhir.resources.allergyintolerance import AllergyIntolerance
from fhir.resources.condition import Condition
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.observation import Observation as FHIRObservation

from agents.schemas import Allergy, CaseObject, ClinicalCode, Medication, Observation
from shadi_fhir.exceptions import FHIRValidationError

logger = structlog.get_logger()


def _age_from_birth_date(birth_date: str | None) -> int | None:
    if not birth_date:
        return None
    try:
        bd = date.fromisoformat(birth_date[:10])
    except ValueError:
        return None
    today = date.today()
    years = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    return max(0, years)


def _map_gender(raw: str | None) -> str | None:
    if not raw:
        return None
    g = raw.lower()
    if g in ("male", "m"):
        return "male"
    if g in ("female", "f"):
        return "female"
    if g in ("other", "unknown"):
        return "other"
    return "other"


def _resource_index(bundle_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map ``ResourceType/id`` (and bare ``id``) to resource dicts in the bundle."""
    index: dict[str, dict[str, Any]] = {}
    for entry in bundle_json.get("entry") or []:
        res = entry.get("resource")
        if not isinstance(res, dict):
            continue
        rid = res.get("id")
        rtype = res.get("resourceType")
        if rid and rtype:
            index[f"{rtype}/{rid}"] = res
            index[rid] = res
    return index


def _resolve_reference(ref: str | None, by_key: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not ref:
        return None
    ref = ref.strip()
    if ref in by_key:
        return by_key[ref]
    tail = ref.rsplit("/", 2)
    if len(tail) >= 2:
        key = f"{tail[-2]}/{tail[-1]}"
        if key in by_key:
            return by_key[key]
    m = re.search(r"([A-Za-z]+)/([A-Za-z0-9.\-]+)$", ref)
    if m:
        key = f"{m.group(1)}/{m.group(2)}"
        return by_key.get(key)
    return None


def _chief_complaint_r4(encounter: dict[str, Any], by_key: dict[str, dict[str, Any]]) -> str:
    """R4: ``reasonCode`` / ``reasonReference``."""
    for rc in encounter.get("reasonCode") or []:
        if not isinstance(rc, dict):
            continue
        if rc.get("text"):
            return str(rc["text"])
        codings = rc.get("coding") or []
        if codings and isinstance(codings[0], dict):
            disp = codings[0].get("display")
            if disp:
                return str(disp)
            code = codings[0].get("code")
            if code:
                return str(code)
    for rr in encounter.get("reasonReference") or []:
        if not isinstance(rr, dict):
            continue
        ref = rr.get("reference")
        target = _resolve_reference(ref, by_key)
        if target and target.get("resourceType") == "Condition":
            return _condition_display_r4(target)
    return ""


def _condition_display_r4(cond: dict[str, Any]) -> str:
    code = cond.get("code")
    if not isinstance(code, dict):
        return ""
    if code.get("text"):
        return str(code["text"])
    codings = code.get("coding") or []
    if codings and isinstance(codings[0], dict) and codings[0].get("display"):
        return str(codings[0]["display"])
    return ""


def _clinical_code_from_codeable_dict(code: dict[str, Any] | None) -> ClinicalCode | None:
    if not isinstance(code, dict):
        return None
    codings = code.get("coding") or []
    if not codings or not isinstance(codings[0], dict):
        return None
    c = cast(dict[str, Any], codings[0])
    text = str(code.get("text") or "")
    return ClinicalCode(
        system=str(c.get("system") or ""),
        code=str(c.get("code") or ""),
        display=str(c.get("display") or text or ""),
    )


def _clinical_code_from_codeable_concept(concept: Any) -> ClinicalCode | None:
    """Map a FHIR CodeableConcept model to :class:`ClinicalCode`."""
    if concept is None:
        return None
    codings = getattr(concept, "coding", None) or []
    if not codings:
        return None
    c0 = codings[0]
    text = getattr(concept, "text", None) or ""
    return ClinicalCode(
        system=c0.system or "",
        code=c0.code or "",
        display=c0.display or text or "",
    )


def _clinical_code_from_condition_dict(res: dict[str, Any]) -> ClinicalCode | None:
    code = res.get("code")
    return _clinical_code_from_codeable_dict(code if isinstance(code, dict) else None)


def _build_observation(
    loinc_code: str,
    display: str,
    value: str | float | None,
    unit: str | None,
) -> Observation:
    return Observation(
        loinc_code=loinc_code,
        display=display,
        value=value,
        unit=unit,
    )


def _observation_from_dict_r4(res: dict[str, Any]) -> Observation | None:
    code = res.get("code")
    if not isinstance(code, dict):
        return None
    codings = code.get("coding") or []
    if not codings or not isinstance(codings[0], dict):
        return None
    c = cast(dict[str, Any], codings[0])
    value: str | float | None = None
    unit: str | None = None
    vq = res.get("valueQuantity")
    if isinstance(vq, dict):
        value = vq.get("value")
        unit = vq.get("unit")
    elif res.get("valueString") is not None:
        value = res.get("valueString")
    return _build_observation(
        str(c.get("code") or ""),
        str(c.get("display") or ""),
        value,
        unit,
    )


def _medication_from_rxnorm_and_name(rxnorm: str, name: str) -> Medication:
    return Medication(rxnorm_code=rxnorm or "", name=name)


def _medication_from_dict_r4(res: dict[str, Any]) -> Medication | None:
    mc = res.get("medicationCodeableConcept")
    if not isinstance(mc, dict):
        return None
    codings = mc.get("coding") or []
    rxnorm = ""
    for c in codings:
        if isinstance(c, dict) and "rxnorm" in str(c.get("system") or "").lower():
            rxnorm = str(c.get("code") or "")
            break
    name = str(mc.get("text") or "")
    return _medication_from_rxnorm_and_name(rxnorm, name)


def _manifestation_text_r4(m0: dict[str, Any]) -> str | None:
    """R4: manifestation is CodeableConcept — prefer ``text``, then ``coding[0].display``."""
    if m0.get("text"):
        return str(m0["text"])
    codings = m0.get("coding") or []
    if codings and isinstance(codings[0], dict):
        c0 = cast(dict[str, Any], codings[0])
        disp = c0.get("display")
        if disp:
            return str(disp)
        if c0.get("code"):
            return str(c0["code"])
    return None


def _build_allergy(
    substance: str,
    rxnorm: str | None,
    reaction: str | None,
    severity: str | None,
) -> Allergy:
    return Allergy(
        substance=substance,
        rxnorm_code=rxnorm,
        reaction=reaction,
        severity=severity,
    )


def _allergy_from_dict_r4(res: dict[str, Any]) -> Allergy | None:
    code = res.get("code")
    if not isinstance(code, dict):
        return None
    codings = code.get("coding") or []
    rxnorm = None
    for c in codings:
        if isinstance(c, dict) and "rxnorm" in str(c.get("system") or "").lower():
            rxnorm = str(c.get("code") or "")
            break
    substance = str(code.get("text") or "")
    reaction: str | None = None
    severity: str | None = None
    reacts = res.get("reaction") or []
    if reacts and isinstance(reacts[0], dict):
        r0 = cast(dict[str, Any], reacts[0])
        if r0.get("severity"):
            severity = str(r0["severity"])
        mans = r0.get("manifestation") or []
        if mans and isinstance(mans[0], dict):
            reaction = _manifestation_text_r4(cast(dict[str, Any], mans[0]))
    return _build_allergy(substance, rxnorm, reaction, severity)


class FHIRNormalizer:
    """Converts FHIR resource bundles into CaseObject instances."""

    def normalize_condition(self, resource: Condition) -> ClinicalCode | None:
        return _clinical_code_from_codeable_concept(resource.code)

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
        return _build_observation(
            coding.code or "",
            coding.display or "",
            value,
            unit,
        )

    def normalize_medication(self, resource: MedicationRequest) -> Medication | None:
        if not resource.medicationCodeableConcept:
            return None
        codings = resource.medicationCodeableConcept.coding or []
        rxnorm = next((c.code for c in codings if "rxnorm" in (c.system or "").lower()), "")
        name = resource.medicationCodeableConcept.text or ""
        return _medication_from_rxnorm_and_name(rxnorm or "", name or "")

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
                m0 = r.manifestation[0]
                md = m0.model_dump(mode="json", exclude_none=True)
                if isinstance(md, dict):
                    reaction = _manifestation_text_r4(md)
                if reaction is None and m0.text:
                    reaction = m0.text
            if r.severity:
                severity = r.severity
        return _build_allergy(substance, rxnorm, reaction, severity)

    def bundle_to_case(self, bundle_json: dict[str, Any]) -> CaseObject:
        """Parse a FHIR R4 ``Bundle`` (dict) into a :class:`CaseObject`."""
        entries = bundle_json.get("entry")
        if not isinstance(entries, list):
            raise FHIRValidationError("Bundle has no entry list")

        by_key = _resource_index(bundle_json)
        patient_id: str | None = None
        age: int | None = None
        sex: str | None = None
        encounter_id: str | None = None
        chief_complaint: str | None = None
        conditions: list[ClinicalCode] = []
        observations: list[Observation] = []
        medications: list[Medication] = []
        allergies: list[Allergy] = []

        for entry in entries:
            res = entry.get("resource") if isinstance(entry, dict) else None
            if not isinstance(res, dict):
                continue
            rtype = res.get("resourceType")
            if rtype == "Patient":
                pid = res.get("id")
                if isinstance(pid, str) and pid:
                    patient_id = pid
                    age = _age_from_birth_date(res.get("birthDate"))
                    sex = _map_gender(res.get("gender"))
            elif rtype == "Encounter":
                eid = res.get("id")
                if isinstance(eid, str) and eid:
                    encounter_id = eid
                    chief_complaint = _chief_complaint_r4(res, by_key)
            elif rtype == "Condition":
                cc = _clinical_code_from_condition_dict(res)
                if cc:
                    conditions.append(cc)
            elif rtype == "Observation":
                obs = _observation_from_dict_r4(res)
                if obs:
                    observations.append(obs)
            elif rtype == "MedicationRequest":
                med = _medication_from_dict_r4(res)
                if med:
                    medications.append(med)
            elif rtype == "AllergyIntolerance":
                al = _allergy_from_dict_r4(res)
                if al:
                    allergies.append(al)

        if not patient_id:
            raise FHIRValidationError("Bundle must include a Patient with id")
        if not encounter_id:
            raise FHIRValidationError("Bundle must include an Encounter with id")

        return CaseObject(
            patient_id=patient_id,
            encounter_id=encounter_id,
            chief_complaint=chief_complaint or "",
            triage_notes_raw="",
            conditions=conditions,
            observations=observations,
            medications=medications,
            allergies=allergies,
            age=age,
            sex=sex,
        )
