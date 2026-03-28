"""Diagnostic pipeline job (backend #33).

DEP-2 (cross-track-dependencies): swap stub fallback for a hard dependency on
``Orchestrator().run`` once Joshua #39 is merged and the job signature is frozen.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog

from agents.orchestrator.orchestrator import Orchestrator
from agents.schemas import CaseObject, DifferentialReport

logger = structlog.get_logger()


def _fixture_report(case_id: UUID) -> DifferentialReport:
    path = Path(__file__).resolve().parent / "fixtures" / "sample_report.json"
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    raw["case_id"] = str(case_id)
    return DifferentialReport.model_validate(raw)


def _parse_case_payload(raw: Any) -> CaseObject:
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw
    return CaseObject.model_validate(data)


async def run_diagnostic_pipeline(ctx: dict[str, Any], case_id: str) -> None:
    """arq entrypoint — ``ctx`` must include asyncpg ``pool`` (see ``tasks.worker``)."""
    pool = ctx["pool"]
    cid = UUID(case_id)
    log = logger.bind(case_id=case_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT case_json FROM cases WHERE id = $1",
            cid,
        )
    if row is None:
        log.warning("pipeline.case_missing")
        return

    case = _parse_case_payload(row["case_json"])

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE cases
            SET status = $2, error_message = NULL, updated_at = NOW()
            WHERE id = $1
            """,
            cid,
            "processing",
        )

    orchestrator_error: str | None = None
    try:
        report = await Orchestrator().run(case)
    except Exception as exc:  # noqa: BLE001 — deliberate stub until #39
        log.warning("orchestrator_stub_fallback", err=str(exc), exc_info=True)
        orchestrator_error = traceback.format_exc()
        report = _fixture_report(cid)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE cases
            SET report_json = $2::jsonb,
                status = $3,
                error_message = $4,
                updated_at = NOW()
            WHERE id = $1
            """,
            cid,
            json.dumps(report.model_dump(mode="json")),
            "complete",
            orchestrator_error,
        )
    log.info("pipeline.complete")
