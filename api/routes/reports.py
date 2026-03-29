"""Diagnostic report routes (backend #33)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.schemas import DiagnosisCandidate, VetoDecision
from api.deps import PoolDep

router = APIRouter()


class ReportStatusResponse(BaseModel):
    status: str
    error: str | None = None


class ReportResponse(BaseModel):
    """Status-aware report response.

    Always returns 200 so the dashboard can poll a single endpoint without
    distinguishing 404 (not-ready) from an actual missing case.  When the
    pipeline is still running, ``top_diagnoses`` is empty and ``status``
    is one of the in-progress values (``queued`` / ``processing``).
    """

    case_id: str
    status: str
    top_diagnoses: list[DiagnosisCandidate] = []
    consensus_level: float = 0.0
    divergent_agents: list[str] = []
    vetoed_recommendations: list[VetoDecision] = []
    completed_at: str | None = None
    error_message: str | None = None


@router.get("/{case_id}/status")
async def report_status(case_id: UUID, pool: PoolDep) -> ReportStatusResponse:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, error_message FROM cases WHERE id = $1",
            case_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return ReportStatusResponse(status=row["status"], error=row["error_message"])


@router.get("/{case_id}")
async def get_report(case_id: UUID, pool: PoolDep) -> ReportResponse:
    """Return the diagnostic report for a case.

    Returns 200 in all non-error states so the dashboard polling loop can
    read ``status`` without needing a separate ``/status`` call.  A 404 is
    only raised when the case does not exist at all.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT report_json, status, updated_at, error_message FROM cases WHERE id = $1",
            case_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")

    status: str = row["status"]
    completed_at: str | None = None
    if status == "complete" and row["updated_at"]:
        completed_at = row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else str(row["updated_at"])

    if status != "complete" or row["report_json"] is None:
        return ReportResponse(
            case_id=str(case_id),
            status=status,
            error_message=row["error_message"],
        )

    report_data: dict[str, Any] = (
        json.loads(row["report_json"])
        if isinstance(row["report_json"], str)
        else row["report_json"]
    )
    return ReportResponse(
        case_id=str(case_id),
        status=status,
        top_diagnoses=report_data.get("top_diagnoses", []),
        consensus_level=report_data.get("consensus_level", 0.0),
        divergent_agents=report_data.get("divergent_agents", []),
        vetoed_recommendations=report_data.get("vetoed_recommendations", []),
        completed_at=completed_at,
        error_message=row["error_message"],
    )
