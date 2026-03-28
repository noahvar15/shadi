"""Intake agent — extracts structured clinical codes from raw triage notes.

Model: qwen2.5:7b via Ollama (see ADR-002)
Inference server: OLLAMA_BASE_URL

The agent sends the raw triage notes to the model in JSON-object mode and
expects a response with three top-level keys:

    conditions   : list of SNOMED CT coded entries
    observations : list of LOINC-coded observations
    medications  : list of RxNorm-coded medications

Structured values are returned from :meth:`reason` in ``SpecialistResult.metadata``
under :data:`INTAKE_CODES_METADATA_KEY`, then merged onto the live ``CaseObject``
in :meth:`post_reason` so :meth:`reason` does not mutate shared state (see
:class:`~agents.base.BaseAgent`).
"""

from __future__ import annotations

import json

from agents._llm import call_chat
from agents.base import BaseAgent
from agents.schemas import (
    CaseObject,
    ClinicalCode,
    Medication,
    Observation,
    SpecialistResult,
)
from config import settings

# Metadata key for structured codes produced by :meth:`IntakeAgent.reason`.
INTAKE_CODES_METADATA_KEY = "intake_codes"

_SYSTEM_PROMPT = """\
You are a clinical informatics assistant. Your task is to extract structured
medical codes from free-text triage notes.

Return ONLY valid JSON with exactly three keys:
  "conditions"   : array of objects with keys "system", "code", "display"
                   (use SNOMED CT; system = "http://snomed.info/sct")
  "observations" : array of objects with keys "loinc_code", "display",
                   and optionally "value" (number or string) and "unit"
                   (use LOINC codes)
  "medications"  : array of objects with keys "rxnorm_code", "name",
                   and optionally "dose" and "route"
                   (use RxNorm codes)

If a category has no findings, return an empty array for that key.
Do not include any explanation outside the JSON object.
"""


def merge_intake_codes_into_case(case: CaseObject, result: SpecialistResult) -> None:
    """Apply intake structured codes from ``result`` onto ``case`` (orchestrator helper)."""
    block = result.metadata.get(INTAKE_CODES_METADATA_KEY)
    if not isinstance(block, dict):
        return
    case.conditions = [ClinicalCode(**x) for x in block.get("conditions", [])]
    case.observations = [Observation(**x) for x in block.get("observations", [])]
    case.medications = [Medication(**x) for x in block.get("medications", [])]


class IntakeAgent(BaseAgent[SpecialistResult]):
    """Extracts SNOMED/LOINC/RxNorm codes from raw triage notes."""

    name = "intake"
    domain = "intake"
    model = "qwen2.5:7b"
    inference_url = settings.OLLAMA_BASE_URL

    async def reason(self, case: CaseObject) -> SpecialistResult:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Chief complaint: {case.chief_complaint}\n\n"
                    f"Triage notes:\n{case.triage_notes_raw}"
                ),
            },
        ]

        raw = await call_chat(
            self.inference_url,
            self.model,
            messages,
            response_format={"type": "json_object"},
            mock_domain=self.domain,
        )

        payload: dict = json.loads(raw)

        conditions = [ClinicalCode(**item) for item in payload.get("conditions", [])]
        observations = [Observation(**item) for item in payload.get("observations", [])]
        medications = [Medication(**item) for item in payload.get("medications", [])]

        return SpecialistResult(
            agent_name=self.name,
            case_id=case.case_id,
            domain=self.domain,
            metadata={
                INTAKE_CODES_METADATA_KEY: {
                    "conditions": [c.model_dump(mode="json") for c in conditions],
                    "observations": [o.model_dump(mode="json") for o in observations],
                    "medications": [m.model_dump(mode="json") for m in medications],
                }
            },
        )

    def post_reason(self, case: CaseObject, result: SpecialistResult) -> None:
        merge_intake_codes_into_case(case, result)
