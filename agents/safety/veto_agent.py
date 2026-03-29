"""Safety veto agent.

Evaluates every next-step recommendation in a ``DifferentialReport`` against
the patient's current medications and allergies using phi4:14b (Ollama).

Per ADR-002, phi4:14b is assigned to hard-constraint checking (logical
constraint satisfaction) and runs on Ollama rather than vLLM.

Checks performed
----------------
1. Drug interactions with current medications
2. Allergy contraindications (e.g. penicillin class for a penicillin-allergic patient)
3. Missing critical workup (e.g. PE rule-out recommended without ordering D-dimer/CT-PA)

Orchestrator contract
---------------------
The orchestrator records vetoed items on the report via
``report.vetoed_recommendations``; the caller decides how to handle vetoes.

Mock mode
---------
When ``settings.MOCK_LLM`` is ``True`` (default for local development) the
phi4 call is skipped entirely and all decisions are returned as
``vetoed=False``.
"""

from __future__ import annotations

import json
import time

import structlog

from agents._llm import call_chat
from agents.base import BaseAgent
from agents.schemas import (
    Allergy,
    CaseObject,
    DifferentialReport,
    Medication,
    SafetyResult,
    VetoDecision,
)
from config import settings

logger = structlog.get_logger()

_SAFETY_SYSTEM = """\
You are a clinical safety reviewer. Given a patient's current medications and
allergies, evaluate each numbered next-step recommendation for potential
safety issues.

For each recommendation check:
1. Drug interactions with the listed medications
2. Allergy contraindications (including cross-reactive drug classes)
3. Missing critical workup (e.g. a pulmonary embolism rule-out recommended
   without ordering D-dimer or CT-PA)

Reply with ONLY valid JSON matching this exact schema — one entry per
recommendation in the same order:
{
  "decisions": [
    {
      "recommendation": "<exact recommendation text>",
      "vetoed": true,
      "reason": "<one-sentence explanation>",
      "contraindication_codes": ["<RxNorm or SNOMED code>"]
    }
  ]
}
Set "vetoed" to false and "reason" to null when the recommendation is safe.
"""

_SAFETY_USER = """\
Patient medications:
{medications}

Patient allergies:
{allergies}

Recommendations to evaluate:
{recommendations}
"""


def _format_medications(medications: list[Medication]) -> str:
    if not medications:
        return "None documented"
    lines = []
    for med in medications:
        parts = [med.name]
        if med.dose:
            parts.append(med.dose)
        if med.route:
            parts.append(f"({med.route})")
        parts.append(f"[RxNorm: {med.rxnorm_code}]")
        lines.append("- " + " ".join(parts))
    return "\n".join(lines)


def _format_allergies(allergies: list[Allergy]) -> str:
    if not allergies:
        return "None documented"
    lines = []
    for allergy in allergies:
        parts = [allergy.substance]
        if allergy.reaction:
            parts.append(f"→ {allergy.reaction}")
        if allergy.severity:
            parts.append(f"({allergy.severity})")
        if allergy.rxnorm_code:
            parts.append(f"[RxNorm: {allergy.rxnorm_code}]")
        lines.append("- " + " ".join(parts))
    return "\n".join(lines)


def _collect_recommendations(report: DifferentialReport) -> list[str]:
    """Flatten all next_steps from every top diagnosis into a single ordered list."""
    recs: list[str] = []
    for diagnosis in report.top_diagnoses:
        recs.extend(diagnosis.next_steps)
    return recs


class SafetyVetoAgent(BaseAgent[SafetyResult]):
    """Hard-constraint safety checker using phi4:14b on Ollama."""

    name = "safety-veto"
    domain = "safety"
    model = settings.SAFETY_MODEL
    inference_url = settings.OLLAMA_BASE_URL

    # -------------------------------------------------------------------------
    # Public interface — overrides BaseAgent.run to accept a DifferentialReport
    # -------------------------------------------------------------------------

    async def run(
        self,
        case: CaseObject,
        report: DifferentialReport | None = None,
    ) -> SafetyResult:
        """Run safety veto checking and return a ``SafetyResult``.

        Parameters
        ----------
        case:
            The patient case providing ``medications`` and ``allergies``.
        report:
            Required. The synthesized differential report whose
            ``top_diagnoses[*].next_steps`` are evaluated. Passing ``None``
            raises ``ValueError`` immediately so callers get a clear error
            rather than a silent no-op.
        """
        if report is None:
            raise ValueError(
                "SafetyVetoAgent.run requires a DifferentialReport; "
                "call agent.run(case, report) not agent.run(case)"
            )
        start = time.monotonic()
        log = logger.bind(agent=self.name, domain=self.domain, model=self.model)
        log.info("agent.start", case_id=case.case_id)
        try:
            result = await self.reason(case, report)
            elapsed_ms = (time.monotonic() - start) * 1000
            log.info(
                "agent.complete",
                case_id=case.case_id,
                elapsed_ms=round(elapsed_ms, 1),
                vetoed_count=sum(1 for d in result.decisions if d.vetoed),
            )
            return result
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000
            log.exception(
                "agent.error",
                case_id=case.case_id,
                elapsed_ms=round(elapsed_ms, 1),
            )
            raise

    async def reason(  # type: ignore[override]
        self,
        case: CaseObject,
        report: DifferentialReport,
    ) -> SafetyResult:
        """Evaluate every next-step recommendation against patient safety constraints.

        Parameters
        ----------
        case:
            The patient case providing ``medications`` and ``allergies``.
        report:
            The differential report whose ``top_diagnoses[*].next_steps`` are
            evaluated.

        Returns
        -------
        SafetyResult
            One ``VetoDecision`` per recommendation from the report, in order.
        """
        recommendations = _collect_recommendations(report)

        if settings.MOCK_LLM:
            decisions = [
                VetoDecision(recommendation=rec, vetoed=False)
                for rec in recommendations
            ]
            return SafetyResult(
                decisions=decisions,
                agent_name=self.name,
                case_id=case.case_id,
            )

        if not recommendations:
            return SafetyResult(
                decisions=[],
                agent_name=self.name,
                case_id=case.case_id,
            )

        numbered_recs = "\n".join(
            f"{i + 1}. {rec}" for i, rec in enumerate(recommendations)
        )
        user_content = _SAFETY_USER.format(
            medications=_format_medications(case.medications),
            allergies=_format_allergies(case.allergies),
            recommendations=numbered_recs,
        )
        messages = [
            {"role": "system", "content": _SAFETY_SYSTEM},
            {"role": "user", "content": user_content},
        ]

        raw = await call_chat(
            self.inference_url,
            self.model,
            messages,
            response_format={"type": "json_object"},
            mock_domain=self.domain,
        )

        decisions, parse_error = self._parse_decisions(raw, recommendations)
        return SafetyResult(
            decisions=decisions,
            agent_name=self.name,
            case_id=case.case_id,
            parse_error=parse_error,
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _parse_decisions(
        self,
        raw: str,
        recommendations: list[str],
    ) -> tuple[list[VetoDecision], bool]:
        """Parse phi4's JSON response into a ``(decisions, parse_error)`` tuple.

        Returns
        -------
        decisions:
            One ``VetoDecision`` per recommendation.
        parse_error:
            ``True`` when the response could not be parsed or was truncated.
            All decisions are returned as ``vetoed=True`` (fail-closed) so the
            orchestrator halts safely rather than silently passing an
            unreviewed recommendation.
        """
        try:
            payload = json.loads(raw)
            raw_decisions: list[dict] = payload.get("decisions", [])
            if len(raw_decisions) < len(recommendations):
                raise ValueError(
                    f"phi4 returned {len(raw_decisions)} decision(s) for "
                    f"{len(recommendations)} recommendation(s); "
                    "partial response treated as parse error"
                )
            decisions: list[VetoDecision] = []
            for i, rec in enumerate(recommendations):
                entry = raw_decisions[i]
                decisions.append(
                    VetoDecision(
                        recommendation=rec,
                        vetoed=bool(entry.get("vetoed", False)),
                        reason=entry.get("reason") or None,
                        contraindication_codes=list(
                            entry.get("contraindication_codes", [])
                        ),
                    )
                )
            return decisions, False
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.error(
                "safety_veto.parse_error",
                raw_preview=raw[:200],
            )
            return (
                [VetoDecision(recommendation=rec, vetoed=True) for rec in recommendations],
                True,
            )
