"""Diagnostic report routes (backend #33)."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.schemas import DifferentialReport
from api.deps import PoolDep

router = APIRouter()


class ReportStatusResponse(BaseModel):
    status: str
    error: str | None = None


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
async def get_report(case_id: UUID, pool: PoolDep) -> DifferentialReport:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT report_json, status FROM cases WHERE id = $1",
            case_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if row["status"] != "complete" or row["report_json"] is None:
        raise HTTPException(status_code=404, detail="Report not ready")

    raw = row["report_json"]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail="Stored report is invalid JSON") from e
    return DifferentialReport.model_validate(raw)
