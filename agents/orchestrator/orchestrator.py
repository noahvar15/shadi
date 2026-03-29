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
from collections.abc import Awaitable, Callable

import structlog
from pydantic import ValidationError

from a2a.debate import DebateManager
from a2a.protocol import A2AMessage, MessageIntent
from agents._llm import call_chat
from agents.evidence.evidence_agent import EvidenceAgent
from agents.safety.veto_agent import SafetyVetoAgent
from agents.schemas import CaseObject, DiagnosisCandidate, DifferentialReport, EvidenceResult, SafetyResult, SpecialistResult
from agents.specialists.cardiology_agent import CardiologyAgent
from agents.specialists.neurology_agent import NeurologyAgent
from agents.specialists.pulmonology_agent import PulmonologyAgent
from agents.specialists.toxicology_agent import ToxicologyAgent
from config import settings

logger = structlog.get_logger()

_SYNTHESIS_SYSTEM = """\
You are a senior attending emergency medicine physician synthesizing a
multi-specialty differential diagnosis in an ED setting.

You will receive specialist findings from cardiology, neurology, pulmonology,
and toxicology. Each specialist may provide structured diagnoses and/or
free-text reasoning traces. USE ALL AVAILABLE INFORMATION — even if structured
diagnoses are sparse, the reasoning traces contain valuable clinical thinking.

Your task:
1. Review ALL specialist reasoning and diagnoses
2. Identify the most clinically important differential diagnoses
3. Rank them by likelihood given the clinical presentation
4. Include actionable next steps for the emergency physician

Reply ONLY with valid JSON:
{
  "top_diagnoses": [
    {
      "rank": 1,
      "display": "Diagnosis name",
      "confidence": 0.65,
      "snomed_code": "optional SNOMED CT code",
      "next_steps": ["Specific test or action"],
      "flags": ["URGENT if time-critical"]
    }
  ]
}

IMPORTANT:
- You MUST provide at least 3 diagnoses, up to 5
- Each diagnosis MUST have a clear "display" name and numeric "confidence" (0.0-1.0)
- Confidences across all diagnoses should sum to approximately 1.0
- next_steps should be specific, actionable orders for the ED (labs, imaging, consults)
- Even if specialist data is limited, use your clinical knowledge to generate a reasonable differential
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

    async def run(
        self,
        case: CaseObject,
        on_step: Callable[[str], Awaitable[None]] | None = None,
    ) -> DifferentialReport:
        log = logger.bind(case_id=str(case.case_id))
        log.info("orchestrator.run.start")

        async def _step(name: str) -> None:
            if on_step:
                await on_step(name)

        # ── 1. Specialist reasoning (parallel or sequential — see SPECIALISTS_PARALLEL) ─
        await _step("specialists")
        if settings.SPECIALISTS_PARALLEL:
            raw_results = await asyncio.gather(
                *[agent.run(case) for agent in self._specialists],
                return_exceptions=True,
            )
        else:
            raw_results = []
            for agent in self._specialists:
                try:
                    raw_results.append(await agent.run(case))
                except BaseException as exc:  # noqa: BLE001 — mirror gather(return_exceptions=True)
                    raw_results.append(exc)
        specialist_results: list[SpecialistResult] = []
        for agent, outcome in zip(self._specialists, raw_results):
            if isinstance(outcome, BaseException):
                log.warning(
                    "orchestrator.specialist.failed",
                    agent=agent.name,
                    error=str(outcome),
                )
                specialist_results.append(
                    SpecialistResult(
                        agent_name=agent.name,
                        case_id=case.case_id,
                        domain=agent.domain,
                        diagnoses=[],
                        reasoning_trace=f"Agent unavailable: {outcome}",
                    )
                )
            else:
                specialist_results.append(outcome)
        log.info("orchestrator.specialists.done", count=len(specialist_results))

        # ── 2. Evidence grounding ──────────────────────────────────────────────
        await _step("evidence")
        try:
            evidence_result = await self._evidence_agent.run(case, list(specialist_results))
        except Exception as exc:
            log.warning("orchestrator.evidence.failed", error=str(exc))
            all_diagnoses = [dx for sr in specialist_results for dx in sr.diagnoses]
            evidence_result = EvidenceResult(
                agent_name="evidence",
                case_id=case.case_id,
                domain="evidence",
                grounded_diagnoses=all_diagnoses,
            )
        log.info("orchestrator.evidence.done", grounded=len(evidence_result.grounded_diagnoses))

        # ── 3. A2A debate ─────────────────────────────────────────────────────
        await _step("debate")
        debate = DebateManager(case_id=case.case_id)
        round_ = debate.open_round()
        for sr in specialist_results:
            for dx in sr.diagnoses:
                if dx.confidence >= 0.2:
                    debate.add_message(A2AMessage(
                        sender=sr.agent_name,
                        recipient="orchestrator",
                        case_id=case.case_id,
                        intent=MessageIntent.ENDORSE,
                        target_diagnosis=dx.display,
                        target_diagnosis_snomed=dx.snomed_code,
                        argument=(
                            f"{sr.agent_name} endorses {dx.display} "
                            f"(rank {dx.rank}, confidence {dx.confidence:.2f})"
                        ),
                    ))
                else:
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
        await _step("synthesis")
        synthesis_user = json.dumps({
            "specialist_findings": [
                {
                    "agent": sr.agent_name,
                    "domain": sr.domain,
                    "reasoning_trace": sr.reasoning_trace or "(no reasoning provided)",
                    "diagnoses": [
                        d.model_dump(exclude={"supporting_evidence"})
                        for d in sr.diagnoses
                    ],
                }
                for sr in specialist_results
            ],
            "consensus_scores": consensus,
            "divergent_diagnoses": divergent,
            "patient_chief_complaint": case.chief_complaint,
        })
        # #region agent log
        import time as _time
        _log_entry = json.dumps({"sessionId": "4f5ee4", "location": "orchestrator.py:synthesis_input", "message": "synthesis input data", "data": {"specialist_dx_counts": [len(sr.diagnoses) for sr in specialist_results], "has_reasoning": [bool(sr.reasoning_trace) for sr in specialist_results], "consensus_entries": len(consensus), "consensus": consensus, "divergent": divergent}, "timestamp": int(_time.time() * 1000), "hypothesisId": "H5", "runId": "pre-fix"})
        try:
            with open("/home/yconic/Documents/shadi/.cursor/debug-4f5ee4.log", "a") as _f:
                _f.write(_log_entry + "\n")
        except OSError:
            pass
        # #endregion
        raw = ""
        try:
            raw = await call_chat(
                settings.OLLAMA_BASE_URL,
                settings.ORCHESTRATOR_MODEL,
                [
                    {"role": "system", "content": _SYNTHESIS_SYSTEM},
                    {"role": "user", "content": synthesis_user},
                ],
                response_format={"type": "json_object"},
                mock_domain="orchestrator",
            )
            cleaned_raw = raw.strip()
            if cleaned_raw.startswith("```"):
                import re
                m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", cleaned_raw, re.DOTALL)
                if m:
                    cleaned_raw = m.group(1).strip()
            payload = json.loads(cleaned_raw)
            raw_top = payload.get("top_diagnoses", [])
            top_diagnoses: list[DiagnosisCandidate] = []
            for i, d in enumerate(raw_top):
                try:
                    if "rank" not in d:
                        d["rank"] = i + 1
                    if isinstance(d.get("confidence"), str):
                        d["confidence"] = float(d["confidence"])
                    top_diagnoses.append(DiagnosisCandidate(**{
                        k: v for k, v in d.items()
                        if k in DiagnosisCandidate.model_fields
                    }))
                except (ValidationError, ValueError) as dx_exc:
                    log.warning("orchestrator.synthesis.dx_skip", index=i, error=str(dx_exc))
        except (json.JSONDecodeError, ValidationError) as exc:
            log.error(
                "orchestrator.synthesis.parse_error",
                error=str(exc),
                raw=raw[:500],
            )
            top_diagnoses = []
        except Exception as exc:
            log.error(
                "orchestrator.synthesis.call_error",
                error=str(exc),
            )
            top_diagnoses = []
        # #region agent log
        _synth_log = json.dumps({"sessionId": "4f5ee4", "location": "orchestrator.py:synthesis_output", "message": "synthesis result", "data": {"raw_preview": raw[:500], "top_diagnoses_count": len(top_diagnoses), "diagnoses": [d.model_dump(exclude={"supporting_evidence"}) for d in top_diagnoses]}, "timestamp": int(_time.time() * 1000), "hypothesisId": "H5", "runId": "pre-fix"})
        try:
            with open("/home/yconic/Documents/shadi/.cursor/debug-4f5ee4.log", "a") as _f:
                _f.write(_synth_log + "\n")
        except OSError:
            pass
        # #endregion
        log.info("orchestrator.synthesis.done", top_diagnoses_count=len(top_diagnoses))

        report = DifferentialReport(
            case_id=case.case_id,
            top_diagnoses=top_diagnoses,
            consensus_level=sum(consensus.values()) / max(len(consensus), 1),
            divergent_agents=divergent,
        )

        # ── 5. Safety veto ────────────────────────────────────────────────────
        await _step("safety")
        # Runs after synthesis so it can inspect the assembled recommendations.
        # If any decision is vetoed, the vetoed items are recorded on the report
        # and a warning is logged; the orchestrator caller decides whether to halt.
        try:
            safety_result = await self._safety_agent.run(case, report)
        except Exception as exc:
            log.warning("orchestrator.safety.failed", error=str(exc))
            safety_result = SafetyResult(
                agent_name="safety-veto",
                case_id=case.case_id,
                domain="safety",
                decisions=[],
            )
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
