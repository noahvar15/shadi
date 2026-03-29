"""Toxicology specialist agent.

Model: meditron:70b + "toxicology" LoRA adapter via vLLM (see ADR-002)
Inference server: VLLM_BASE_URL

Focuses on:
  - Overdose syndromes (opioid, benzodiazepine, tricyclic, acetaminophen, salicylate)
  - Drug-drug interactions with clinical consequences
  - Environmental / occupational exposures (carbon monoxide, organophosphates)
  - Antidote selection and dosing guidance
  - Toxidrome identification
"""

from __future__ import annotations

import json

from agents._llm import call_chat
from agents.base import BaseAgent
from agents.vllm_openai_ids import specialist_chat_model
from agents.schemas import CaseObject, DiagnosisCandidate, SpecialistResult
from config import settings

_SYSTEM_PROMPT = """\
You are an attending medical toxicologist. Analyse the patient case and
generate a differential diagnosis focused on toxic and pharmacological causes.

Prioritise ruling in or out the following:
  - Opioid toxidrome (overdose, respiratory depression)
  - Sedative-hypnotic toxidrome (benzodiazepine, barbiturate)
  - Tricyclic antidepressant overdose (QRS widening, seizure risk)
  - Acetaminophen (paracetamol) overdose — hepatotoxicity timeline
  - Salicylate toxicity
  - Carbon monoxide poisoning
  - Organophosphate / cholinergic toxidrome
  - Serotonin syndrome
  - Clinically significant drug-drug interactions

Return ONLY valid JSON with exactly two keys:
  "diagnoses"       : array of diagnosis objects (up to 5), each with:
                        "rank"        (integer, 1-based)
                        "display"     (string)
                        "confidence"  (float 0.0–1.0)
                        "snomed_code" (string, optional)
                        "next_steps"  (array of strings — antidotes, labs, monitoring)
                        "flags"       (array of strings, e.g. ["URGENT", "ANTIDOTE_AVAILABLE"])
  "reasoning_trace" : step-by-step toxicology reasoning including toxidrome
                      identification and antidote considerations

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


class ToxicologyAgent(BaseAgent[SpecialistResult]):
    """Toxicology specialist using Meditron-70B + LoRA adapter."""

    name = "toxicology"
    domain = "toxicology"
    model = "toxicology"  # LoRA adapter name on vLLM
    inference_url = settings.VLLM_BASE_URL

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
            specialist_chat_model(self.model),
            messages,
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
