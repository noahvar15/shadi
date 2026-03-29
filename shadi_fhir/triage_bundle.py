"""Build minimal FHIR R4 Bundles from nurse triage text (issue #70).

Canonical demo shape (see ``docs/cross-track-dependencies`` / issue #70):

- ``Patient`` (id)
- ``Encounter`` ``status=arrived`` + ``reasonCode`` short label
- ``Observation`` with LOINC **34109-9** (*History and physical note*) and
  ``valueString`` = full triage narrative → maps to :attr:`CaseObject.triage_notes_raw`

Chief complaint for the case comes from Encounter ``reasonCode`` (existing normalizer).
"""

from __future__ import annotations

from typing import Any

# LOINC: History and physical note — used as the triage narrative carrier for Shadi intake.
LOINC_TRIAGE_NARRATIVE = "34109-9"


def build_triage_bundle(
    *,
    patient_id: str,
    encounter_id: str,
    triage_text: str,
    chief_complaint: str | None = None,
) -> dict[str, Any]:
    """Return a FHIR R4 ``collection`` Bundle dict suitable for :meth:`FHIRNormalizer.bundle_to_case`."""
    pid = patient_id.strip()
    eid = encounter_id.strip()
    if not pid:
        msg = "patient_id must be non-empty"
        raise ValueError(msg)
    if not eid:
        msg = "encounter_id must be non-empty"
        raise ValueError(msg)

    text = triage_text.strip()
    if not text:
        msg = "triage_text must be non-empty"
        raise ValueError(msg)
    cc = chief_complaint.strip() if chief_complaint else ""
    if not cc:
        cc = text if len(text) <= 200 else f"{text[:197]}..."

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": pid,
                    "gender": "unknown",
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": encounter_id,
                    "status": "arrived",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "reasonCode": [{"text": cc}],
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": f"{eid}-hpi",
                    "status": "final",
                    "code": {
                        "coding": [
                            {
                                "system": "http://loinc.org",
                                "code": LOINC_TRIAGE_NARRATIVE,
                                "display": "History and physical note",
                            }
                        ],
                        "text": "Triage narrative",
                    },
                    "subject": {"reference": f"Patient/{pid}"},
                    "valueString": text,
                }
            },
        ],
    }
