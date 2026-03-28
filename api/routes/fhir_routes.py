"""FHIR subscription notification webhook (issue #27)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from agents.schemas import CaseObject
from shadi_fhir.mcp_server import FHIRMCPServer

router = APIRouter()


def _get_mcp(request: Request) -> FHIRMCPServer:
    mcp = getattr(request.app.state, "fhir_mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="FHIR MCP server not configured")
    return mcp


@router.post("/notify")
async def fhir_notify(bundle: dict[str, Any], request: Request) -> CaseObject:
    """Rest-hook endpoint for FHIR Subscription notifications (Encounter)."""
    mcp = _get_mcp(request)
    return await mcp.handle_notification(bundle)
