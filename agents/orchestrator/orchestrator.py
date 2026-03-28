"""Orchestrator — coordinates the full diagnostic pipeline.

Sequence:
  1. Fan-out: dispatch CaseObject to all 4 specialist agents concurrently
  2. Evidence grounding: each specialist result is cross-checked
  3. A2A debate: one round of structured ENDORSE/CHALLENGE/MODIFY messages
  4. Output synthesis: produce a preliminary DifferentialReport
  5. Safety veto: block unsafe recommendations; populate vetoed_recommendations
"""

from __future__ import annotations

import asyncio
import json

import structlog
from pydantic import ValidationError

from a2a.debate import DebateManager
from a2a.protocol import A2AMessage, MessageIntent
from agents._llm import call_chat
from agents.evidence.evidence_agent import EvidenceAgent
from agents.safety.veto_agent import SafetyVetoAgent
from agents.schemas import CaseObject, DiagnosisCandidate, DifferentialReport, SpecialistResult
from agents.specialists.cardiology_agent import CardiologyAgent
from agents.specialists.neurology_agent import NeurologyAgent
from agents.specialists.pulmonology_agent import PulmonologyAgent
from agents.specialists.toxicology_agent import ToxicologyAgent
from config import settings

logger = structlog.get_logger()

_SYNTHESIS_SYSTEM = """\
You are a senior attending physician synthesizing a multi-specialty differential
diagnosis. Given specialist findings, debate consensus scores, and divergent
diagnoses, produce a ranked differential of the top 5 candidates.

Reply ONLY with valid JSON:
{
  "top_diagnoses": [
    {
      "rank": 1,
      "display": "...",
      "confidence": 0.0,
      "snomed_code": "...",
      "next_steps": ["..."],
      "flags": ["..."]
    }
  ]
}
"""


class Orchestrator:
    """Runs the full Shadi pipeline for a single case."""

    def __init__(
        self,
        specialists: list | None = None,
        evidence_agent: EvidenceAgent | None = None,
        safety_agent: SafetyVetoAgent | None = None,
    ) -> None:
        self._specialists: list = specialists or [
            CardiologyAgent(),
            NeurologyAgent(),
            PulmonologyAgent(),
            ToxicologyAgent(),
        ]
        self._evidence_agent: EvidenceAgent = evidence_agent or EvidenceAgent()
        self._safety_agent: SafetyVetoAgent = safety_agent or SafetyVetoAgent()

    async def run(self, case: CaseObject) -> DifferentialReport:
        log = logger.bind(case_id=str(case.case_id))
        log.info("orchestrator.run.start")

        # ── 1. Parallel specialist reasoning ──────────────────────────────────
        specialist_results: list[SpecialistResult] = await asyncio.gather(
            *[agent.run(case) for agent in self._specialists],
            return_exceptions=False,
        )
        log.info("orchestrator.specialists.done", count=len(specialist_results))

        # ── 2. Evidence grounding ──────────────────────────────────────────────
        evidence_result = await self._evidence_agent.run(case, list(specialist_results))
        log.info("orchestrator.evidence.done", grounded=len(evidence_result.grounded_diagnoses))

        # ── 3. A2A debate ─────────────────────────────────────────────────────
        debate = DebateManager(case_id=case.case_id)
        round_ = debate.open_round()
        for sr in specialist_results:
            for dx in sr.diagnoses:
                if dx.rank == 1 and dx.confidence >= 0.4:
                    debate.add_message(A2AMessage(
                        sender=sr.agent_name,
                        recipient="orchestrator",
                        case_id=case.case_id,
                        intent=MessageIntent.ENDORSE,
                        target_diagnosis=dx.display,
                        target_diagnosis_snomed=dx.snomed_code,
                        argument=(
                            f"{sr.agent_name} endorses {dx.display} as primary diagnosis "
                            f"(confidence {dx.confidence:.2f})"
                        ),
                    ))
                elif dx.confidence < 0.4:
                    debate.add_message(A2AMessage(
                        sender=sr.agent_name,
                        recipient="orchestrator",
                        case_id=case.case_id,
                        intent=MessageIntent.CHALLENGE,
                        target_diagnosis=dx.display,
                        target_diagnosis_snomed=dx.snomed_code,
                        argument=(
                            f"{sr.agent_name} challenges {dx.display}: "
                            f"low confidence {dx.confidence:.2f}"
                        ),
                    ))
        debate.close_round()
        consensus = debate.consensus_scores()
        divergent = debate.divergent_diagnoses()
        log.info(
            "orchestrator.debate.done",
            consensus_entries=len(consensus),
            divergent=divergent,
        )

        # ── 4. Synthesis ──────────────────────────────────────────────────────
        synthesis_user = json.dumps({
            "specialist_diagnoses": [
                {
                    "agent": sr.agent_name,
                    "domain": sr.domain,
                    "diagnoses": [
                        d.model_dump(exclude={"supporting_evidence"})
                        for d in sr.diagnoses
                    ],
                }
                for sr in specialist_results
            ],
            "consensus_scores": consensus,
            "divergent_diagnoses": divergent,
        })
        raw = await call_chat(
            settings.OLLAMA_BASE_URL,
            "deepseek-r1:32b",
            [
                {"role": "system", "content": _SYNTHESIS_SYSTEM},
                {"role": "user", "content": synthesis_user},
            ],
            response_format={"type": "json_object"},
            mock_domain="orchestrator",
        )
        try:
            payload = json.loads(raw)
            top_diagnoses = [DiagnosisCandidate(**d) for d in payload.get("top_diagnoses", [])]
        except (json.JSONDecodeError, ValidationError) as exc:
            log.error(
                "orchestrator.synthesis.parse_error",
                error=str(exc),
                raw=raw,
            )
            top_diagnoses = []
        log.info("orchestrator.synthesis.done", top_diagnoses_count=len(top_diagnoses))

        report = DifferentialReport(
            case_id=case.case_id,
            top_diagnoses=top_diagnoses,
            consensus_level=sum(consensus.values()) / max(len(consensus), 1),
            divergent_agents=divergent,
        )

        # ── 5. Safety veto ────────────────────────────────────────────────────
        # Runs after synthesis so it can inspect the assembled recommendations.
        # If any decision is vetoed, the vetoed items are recorded on the report
        # and a warning is logged; the orchestrator caller decides whether to halt.
        safety_result = await self._safety_agent.run(case, report)
        vetoed = [d for d in safety_result.decisions if d.vetoed]
        if vetoed:
            log.warning(
                "orchestrator.safety_veto.halt",
                case_id=str(case.case_id),
                vetoed_count=len(vetoed),
            )
            report = report.model_copy(update={"vetoed_recommendations": vetoed})

        log.info("orchestrator.run.complete")
        return report
