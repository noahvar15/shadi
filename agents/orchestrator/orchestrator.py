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
from uuid import UUID

import structlog

from agents.schemas import CaseObject, DifferentialReport, SpecialistResult
from a2a.debate import DebateManager

logger = structlog.get_logger()


class Orchestrator:
    """Runs the full Shadi pipeline for a single case."""

    def __init__(self) -> None:
        # Agents are injected or constructed here; stubs for now
        self._specialists: list = []  # List[BaseAgent[SpecialistResult]]
        self._evidence_agent = None
        self._safety_agent = None

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
        if self._evidence_agent is not None:
            await self._evidence_agent.run(case, list(specialist_results))

        # ── 3. A2A debate ─────────────────────────────────────────────────────
        debate = DebateManager(case_id=case.case_id)
        round_ = debate.open_round()
        # TODO: collect messages from specialist agents and add to round_
        debate.close_round()
        consensus = debate.consensus_scores()
        divergent = debate.divergent_diagnoses()
        log.info(
            "orchestrator.debate.done",
            consensus_entries=len(consensus),
            divergent=divergent,
        )

        # ── 4. Synthesis ──────────────────────────────────────────────────────
        # TODO: rank and merge specialist diagnoses into DifferentialReport
        report = DifferentialReport(
            case_id=case.case_id,
            consensus_level=sum(consensus.values()) / max(len(consensus), 1),
            divergent_agents=divergent,
        )

        # ── 5. Safety veto ────────────────────────────────────────────────────
        # Runs after synthesis so it can inspect the assembled recommendations.
        # If any decision is vetoed, the vetoed items are recorded on the report
        # and a warning is logged; the orchestrator caller decides whether to halt.
        if self._safety_agent is not None:
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
