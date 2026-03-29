"""Diagnostic pipeline job — runs the full Shadi orchestrator for a single case.

Status lifecycle managed here:
    queued → processing → complete | failed
"""

from __future__ import annotations

import json
import traceback
from typing import Any
from uuid import UUID

import structlog

from agents.orchestrator.orchestrator import Orchestrator
from agents.schemas import CaseObject

logger = structlog.get_logger()


def _parse_case_payload(raw: Any) -> CaseObject:
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw
    return CaseObject.model_validate(data)


async def run_diagnostic_pipeline(ctx: dict[str, Any], case_id: str) -> None:
    """arq entrypoint — ``ctx`` must include asyncpg ``pool`` (set in ``tasks.worker`` startup)."""
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

    try:
        report = await Orchestrator().run(case)
    except Exception as exc:  # noqa: BLE001
        log.error("pipeline.orchestrator_failed", err=str(exc), exc_info=True)
        error_tb = traceback.format_exc()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE cases
                SET status = $2,
                    error_message = $3,
                    updated_at = NOW()
                WHERE id = $1
                """,
                cid,
                "failed",
                error_tb,
            )
        log.info("pipeline.failed")
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE cases
            SET report_json = $2::jsonb,
                status = $3,
                updated_at = NOW()
            WHERE id = $1
            """,
            cid,
            json.dumps(report.model_dump(mode="json")),
            "complete",
        )
    log.info("pipeline.complete")
