"""Image analysis agent — radiology / multimodal interpretation.

Model: alibayram/medgemma:27b via Ollama (see ADR-002)
Inference server: OLLAMA_BASE_URL

If the case carries no ``imaging_attachments`` the agent returns an empty
``SpecialistResult`` immediately so the pipeline does not stall.

When attachments are present each URL is embedded as an image content part in
the multimodal message, mirroring the OpenAI vision API convention that both
Ollama and MedGemma support.

Note: MedGemma multimodal support in Ollama is still stabilising (see ADR-002
unknowns). The ``MOCK_LLM=True`` path exercises the full parsing logic without
requiring the model to be downloaded.
"""

from __future__ import annotations

import json
from typing import Any

from agents._llm import call_chat
from agents.base import BaseAgent
from agents.schemas import CaseObject, DiagnosisCandidate, SpecialistResult
from config import settings

_SYSTEM_PROMPT = """\
You are a radiology consultant reviewing medical imaging attached to a patient
case. Analyse each image carefully and report any significant findings.

Return ONLY valid JSON with exactly two keys:
  "diagnoses"       : array of diagnosis objects, each with:
                        "rank"        (integer, 1-based)
                        "display"     (string description of finding)
                        "confidence"  (float 0.0–1.0)
                        "snomed_code" (string, optional)
                        "flags"       (array of strings, e.g. ["URGENT"])
                        "next_steps"  (array of strings)
  "reasoning_trace" : a brief free-text rationale for your findings

Confidence values across all diagnoses must sum to ≤ 1.0.
If no abnormalities are found, return an empty "diagnoses" array.
"""


class ImageAnalysisAgent(BaseAgent[SpecialistResult]):
    """Interprets medical imaging attachments using MedGemma 27B."""

    name = "image-analysis"
    domain = "imaging"
    model = "alibayram/medgemma:27b"
    inference_url = settings.OLLAMA_BASE_URL

    async def reason(self, case: CaseObject) -> SpecialistResult:
        if not case.imaging_attachments:
            return SpecialistResult(
                agent_name=self.name,
                case_id=case.case_id,
                domain=self.domain,
                diagnoses=[],
                reasoning_trace="No imaging attachments present; skipped.",
            )

        # Build multimodal content: one image_url part per attachment followed
        # by a text part describing the clinical context.
        image_parts: list[dict[str, Any]] = [
            {"type": "image_url", "image_url": {"url": url}}
            for url in case.imaging_attachments
        ]
        image_parts.append(
            {
                "type": "text",
                "text": (
                    f"Patient chief complaint: {case.chief_complaint}\n"
                    f"Age: {case.age or 'unknown'}, Sex: {case.sex or 'unknown'}\n"
                    "Please analyse the attached image(s) for relevant findings."
                ),
            }
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": image_parts},
        ]

        raw = await call_chat(
            self.inference_url,
            self.model,
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
