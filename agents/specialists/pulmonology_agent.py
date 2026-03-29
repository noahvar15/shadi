"""Pulmonology specialist agent.

Model: ``MEDITRON_MODEL`` on Ollama (default ``meditron:70b``); domain via prompt (ADR-004).

Focuses on:
  - Acute respiratory distress syndrome (ARDS)
  - Community-acquired / hospital-acquired pneumonia
  - COPD exacerbation
  - Pulmonary embolism (from a pulmonology perspective)
  - Pneumothorax / tension pneumothorax
  - Pleural effusion
"""

from __future__ import annotations

from agents._llm import call_chat
from agents.base import BaseAgent
from agents.meditron_model_ids import specialist_chat_model
from agents.schemas import CaseObject, SpecialistResult
from agents.specialists._parse import parse_specialist_response
from config import settings

_SYSTEM_PROMPT = """\
You are an attending pulmonologist. Analyse the patient case and generate a
differential diagnosis focused on pulmonary and respiratory causes.

Prioritise ruling in or out the following critical diagnoses:
  - Acute respiratory distress syndrome (ARDS)
  - Community-acquired pneumonia or hospital-acquired pneumonia
  - COPD exacerbation
  - Pulmonary embolism
  - Spontaneous pneumothorax / tension pneumothorax
  - Large pleural effusion
  - Asthma exacerbation

Return ONLY valid JSON with exactly two keys:
  "diagnoses"       : array of diagnosis objects (up to 5), each with:
                        "rank"        (integer, 1-based)
                        "display"     (string)
                        "confidence"  (float 0.0–1.0)
                        "snomed_code" (string, optional)
                        "next_steps"  (array of strings — specific tests/actions)
                        "flags"       (array of strings, e.g. ["URGENT", "EVIDENCE_GAP"])
  "reasoning_trace" : step-by-step pulmonology reasoning

Confidence values across all returned diagnoses must sum to ≤ 1.0.
"""

_USER_TEMPLATE = """\
Chief complaint: {chief_complaint}
Age: {age} | Sex: {sex}

Triage notes:
{triage_notes_raw}

Known conditions: {conditions}
Active medications: {medications}
Allergies: {allergies}
Observations: {observations}
"""


class PulmonologyAgent(BaseAgent[SpecialistResult]):
    """Pulmonology specialist using Ollama Meditron."""

    name = "pulmonology"
    domain = "pulmonology"
    model = settings.MEDITRON_MODEL
    inference_url = settings.OLLAMA_BASE_URL

    async def reason(self, case: CaseObject) -> SpecialistResult:
        user_content = _USER_TEMPLATE.format(
            chief_complaint=case.chief_complaint,
            age=case.age or "unknown",
            sex=case.sex or "unknown",
            triage_notes_raw=case.triage_notes_raw,
            conditions=", ".join(c.display for c in case.conditions) or "none",
            medications=", ".join(m.name for m in case.medications) or "none",
            allergies=", ".join(a.substance for a in case.allergies) or "none",
            observations=", ".join(
                f"{o.display}: {o.value} {o.unit or ''}".strip()
                for o in case.observations
            ) or "none",
        )

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        raw = await call_chat(
            self.inference_url,
            specialist_chat_model(self.domain),
            messages,
            response_format={"type": "json_object"},
            mock_domain=self.domain,
        )

        return parse_specialist_response(
            raw,
            agent_name=self.name,
            domain=self.domain,
            case_id=case.case_id,
        )
