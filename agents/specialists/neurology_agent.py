"""Neurology specialist agent.

Model: ``MEDITRON_MODEL`` on Ollama (default ``meditron:70b``); domain via prompt (ADR-004).

Focuses on:
  - Acute ischaemic stroke / haemorrhagic stroke
  - Transient ischaemic attack (TIA)
  - Bacterial / viral meningitis
  - Encephalitis / encephalopathy
  - Seizure disorders (first seizure, status epilepticus)
  - Guillain-Barré syndrome
"""

from __future__ import annotations

import json

from agents._llm import call_chat
from agents.base import BaseAgent
from agents.meditron_model_ids import specialist_chat_model
from agents.schemas import CaseObject, DiagnosisCandidate, SpecialistResult
from config import settings

_SYSTEM_PROMPT = """\
You are an attending neurologist. Analyse the patient case and generate a
differential diagnosis focused on neurological causes.

Prioritise ruling in or out the following critical diagnoses:
  - Acute ischaemic stroke (large-vessel occlusion, lacunar, cardioembolic)
  - Haemorrhagic stroke (intracerebral, subarachnoid)
  - Transient ischaemic attack (TIA)
  - Bacterial meningitis
  - Viral or autoimmune encephalitis
  - First unprovoked seizure or status epilepticus
  - Guillain-Barré syndrome

Return ONLY valid JSON with exactly two keys:
  "diagnoses"       : array of diagnosis objects (up to 5), each with:
                        "rank"        (integer, 1-based)
                        "display"     (string)
                        "confidence"  (float 0.0–1.0)
                        "snomed_code" (string, optional)
                        "next_steps"  (array of strings — specific tests/actions)
                        "flags"       (array of strings, e.g. ["URGENT", "EVIDENCE_GAP"])
  "reasoning_trace" : step-by-step neurology reasoning

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


class NeurologyAgent(BaseAgent[SpecialistResult]):
    """Neurology specialist using Ollama Meditron."""

    name = "neurology"
    domain = "neurology"
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

        payload: dict = json.loads(raw)

        diagnoses = [
            DiagnosisCandidate(**d) for d in payload.get("diagnoses", [])
        ]

        return SpecialistResult(
            agent_name=self.name,
            case_id=case.case_id,
            domain=self.domain,
            diagnoses=diagnoses,
            reasoning_trace=payload.get("reasoning_trace", ""),
        )
