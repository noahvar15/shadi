"""Subprocess entrypoint: full orchestrator + CLI text with MOCK_LLM=false.

Invoked by ``tests/integration/test_shadi_live_cli_output.py``; not collected as a test.
"""

from __future__ import annotations

import asyncio
import os
import sys

# Before any import that loads ``config.settings``.
os.environ["MOCK_LLM"] = "false"

if os.environ.get("SHADI_SKIP_LIVE_PREFLIGHT", "").strip().lower() not in ("1", "true", "yes"):
    from tools.live_preflight import collect_live_preflight_issues

    _errs, _warns = collect_live_preflight_issues()
    for _w in _warns:
        print(f"live preflight warning: {_w}", file=sys.stderr)
    if _errs:
        for _e in _errs:
            print(f"live preflight error: {_e}", file=sys.stderr)
        raise SystemExit(1)

from agents.cli_output import format_shadi_cli_report
from agents.orchestrator.orchestrator import Orchestrator
from agents.schemas import CaseObject


async def _main() -> None:
    case = CaseObject(
        patient_id="live-cli-patient",
        encounter_id="live-cli-encounter",
        chief_complaint="Chest pain",
        triage_notes_raw="Substernal pressure; rule out ACS.",
    )
    report = await Orchestrator().run(case)
    print(format_shadi_cli_report(case, report))


if __name__ == "__main__":
    asyncio.run(_main())
