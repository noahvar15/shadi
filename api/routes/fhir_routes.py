"""FHIR subscription notification webhook (issue #27).

Integrators must POST the **raw** JSON body bytes and set header
``X-Shadi-Signature: sha256=<hex>`` where ``<hex>`` is
``HMAC_SHA256(FHIR_WEBHOOK_SECRET, raw_body)``. The same secret is required in
``api.config.Settings`` (env ``FHIR_WEBHOOK_SECRET``) when the FHIR MCP server
is enabled; the EHR or an edge proxy must perform this signing on each delivery.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fhir.resources.bundle import Bundle
from pydantic import ValidationError

from shadi_fhir.exceptions import FHIRValidationError

if TYPE_CHECKING:
    from shadi_fhir.mcp_server import FHIRMCPServer

router = APIRouter()

# Upper bound for notification bundles (FHIR JSON); reject larger bodies to limit memory per request.
MAX_FHIR_NOTIFY_BODY_BYTES = 5 * 1024 * 1024

WEBHOOK_SIGNATURE_HEADER = "X-Shadi-Signature"
WEBHOOK_SIGNATURE_PREFIX = "sha256="


def _constant_time_hex_eq(a: str, b: str) -> bool:
    """Compare two lowercase hex strings in (mostly) constant time.

    Avoid a length-based early return: that leaks whether the candidate matches
    the expected digest length. :func:`hmac.compare_digest` requires equal
    lengths and raises ``ValueError`` otherwise; treat that as mismatch without
    branching on ``len()`` first.
    """
    try:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
    except ValueError:
        return False


def verify_fhir_webhook_body(raw_body: bytes, signature_header: str | None, secret: str) -> None:
    """Ensure ``raw_body`` was signed with ``secret`` (HMAC-SHA256).

    The caller must send ``X-Shadi-Signature: sha256=<hex>`` where ``<hex>`` is the
    lowercase hex digest of HMAC-SHA256(secret, raw_body).

    Raises:
        HTTPException: 401 if the secret is wrong, the header is missing, or the digest mismatches.
    """
    if not secret.strip():
        raise HTTPException(
            status_code=503,
            detail="FHIR webhook signing secret is not configured",
        )
    if not signature_header or not signature_header.startswith(WEBHOOK_SIGNATURE_PREFIX):
        raise HTTPException(status_code=401, detail="Missing or invalid webhook signature header")
    received = signature_header[len(WEBHOOK_SIGNATURE_PREFIX) :].strip().lower()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not _constant_time_hex_eq(expected, received):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _get_mcp(request: Request) -> FHIRMCPServer:
    mcp = getattr(request.app.state, "fhir_mcp", None)
    if mcp is None:
        raise HTTPException(status_code=503, detail="FHIR MCP server not configured")
    return mcp


def _get_settings(request: Request):
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise HTTPException(status_code=500, detail="Application settings not initialised")
    return settings


async def _read_request_body_limited(request: Request, max_bytes: int) -> bytes:
    """Read the body while enforcing ``max_bytes`` without buffering past the limit."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/notify")
async def fhir_notify(request: Request) -> dict[str, str]:
    """Rest-hook endpoint for FHIR Subscription notifications (Encounter).

    Expects the raw JSON Bundle as the body and an ``X-Shadi-Signature`` header
    (HMAC-SHA256 over the raw body using ``FHIR_WEBHOOK_SECRET``). Malformed bundles
    produce **400** so senders do not retry as if the server failed.

    Returns a minimal acknowledgment (not the full ``CaseObject``) to avoid exposing
    internal shapes to the EHR sender.
    """
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > MAX_FHIR_NOTIFY_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Request body too large")
        except ValueError:
            pass
    settings = _get_settings(request)
    raw = await _read_request_body_limited(request, MAX_FHIR_NOTIFY_BODY_BYTES)
    verify_fhir_webhook_body(
        raw,
        request.headers.get(WEBHOOK_SIGNATURE_HEADER),
        settings.fhir_webhook_secret,
    )
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc
    if not isinstance(bundle, dict):
        raise HTTPException(status_code=400, detail="FHIR notification must be a JSON object")
    try:
        Bundle.model_validate(bundle)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    mcp = _get_mcp(request)
    try:
        await mcp.handle_notification(bundle)
    except FHIRValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "accepted"}
