"""Human-readable CLI formatting for Shadi pipeline output."""

from __future__ import annotations

from agents.schemas import CaseObject, DifferentialReport


def format_shadi_cli_report(case: CaseObject, report: DifferentialReport) -> str:
    """Format a ``DifferentialReport`` and case context for terminal display.

    Intended for demos, ``pytest -s``, and ``python -m tools.shadi_run_case_cli``.
    """
    lines: list[str] = [
        "═" * 64,
        " SHADI — multi-agent differential (CLI)",
        "═" * 64,
        f"Case ID:      {report.case_id}",
        f"Synthesized:  {report.synthesized_at.isoformat()}",
    ]

    if case.chief_complaint or case.triage_notes_raw:
        lines.extend(["", "--- Case ---"])
        if case.chief_complaint:
            lines.append(f"Chief complaint: {case.chief_complaint}")
        if case.triage_notes_raw:
            raw = case.triage_notes_raw
            if len(raw) > 280:
                raw = raw[:277] + "…"
            lines.append(f"Triage notes:    {raw}")

    lines.extend(["", "--- Ranked differential ---"])
    if not report.top_diagnoses:
        lines.append("(no ranked diagnoses)")
    for d in report.top_diagnoses:
        lines.append(f"  {d.rank}. {d.display}")
        lines.append(f"     confidence: {d.confidence:.2f}")
        if d.snomed_code:
            lines.append(f"     SNOMED:     {d.snomed_code}")
        if d.next_steps:
            lines.append(f"     next steps: {', '.join(d.next_steps)}")
        if d.flags:
            lines.append(f"     flags:      {', '.join(d.flags)}")

    lines.extend(
        [
            "",
            "--- A2A debate summary ---",
            f"Consensus level (mean score): {report.consensus_level:.3f}",
        ]
    )
    if report.divergent_agents:
        lines.append(f"Divergent (above threshold):  {', '.join(report.divergent_agents)}")
    else:
        lines.append("Divergent (above threshold):  (none)")

    lines.extend(["", "--- Safety veto ---"])
    if not report.vetoed_recommendations:
        lines.append("No recommendations vetoed.")
    else:
        for v in report.vetoed_recommendations:
            tag = "VETO" if v.vetoed else "OK"
            lines.append(f"  [{tag}] {v.recommendation}")
            if v.reason:
                lines.append(f"        {v.reason}")

    lines.extend(["", "═" * 64])
    return "\n".join(lines)
