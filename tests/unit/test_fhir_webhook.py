"""Tests for FHIR Subscription notify signing, validation, and intake job ids."""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from agents.schemas import CaseObject
from api.routes.fhir_routes import (
    WEBHOOK_SIGNATURE_HEADER,
    router,
    verify_fhir_webhook_body,
)
from shadi_fhir.exceptions import FHIRValidationError
from shadi_fhir.intake_queue import enqueue_intake_case, intake_job_id


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_fhir_webhook_body_accepts_valid_hmac() -> None:
    body = b'{"resourceType":"Bundle","type":"collection"}'
    secret = "unit-test-secret"
    verify_fhir_webhook_body(body, _sign(body, secret), secret)


def test_verify_fhir_webhook_body_rejects_bad_digest() -> None:
    body = b"{}"
    secret = "unit-test-secret"
    with pytest.raises(HTTPException) as exc_info:
        verify_fhir_webhook_body(body, "sha256=" + "0" * 64, secret)
    assert exc_info.value.status_code == 401


def test_verify_fhir_webhook_body_rejects_missing_header() -> None:
    with pytest.raises(HTTPException) as exc_info:
        verify_fhir_webhook_body(b"{}", None, "secret")
    assert exc_info.value.status_code == 401


def test_verify_fhir_webhook_body_empty_secret_503() -> None:
    with pytest.raises(HTTPException) as exc_info:
        verify_fhir_webhook_body(b"{}", "sha256=ab", "")
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_fhir_notify_returns_400_on_validation_error() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/fhir")
    app.state.settings = MagicMock(fhir_webhook_secret="notify-secret")

    mcp = MagicMock()
    mcp.handle_notification = AsyncMock(
        side_effect=FHIRValidationError("Bundle must include a Patient with id")
    )
    app.state.fhir_mcp = mcp

    body = b'{"resourceType":"Bundle","type":"collection","entry":[]}'
    headers = {WEBHOOK_SIGNATURE_HEADER: _sign(body, "notify-secret")}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/fhir/notify", content=body, headers=headers)

    assert r.status_code == 400
    assert "Patient" in r.json()["detail"]


@pytest.mark.asyncio
async def test_fhir_notify_returns_400_on_invalid_json() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/fhir")
    app.state.settings = MagicMock(fhir_webhook_secret="notify-secret")
    app.state.fhir_mcp = MagicMock()

    body = b"not-json"
    headers = {WEBHOOK_SIGNATURE_HEADER: _sign(body, "notify-secret")}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/fhir/notify", content=body, headers=headers)

    assert r.status_code == 400


@pytest.mark.asyncio
async def test_enqueue_intake_case_passes_stable_job_id() -> None:
    case = CaseObject(
        patient_id="P1",
        encounter_id="E1",
        chief_complaint="cough",
        triage_notes_raw="notes",
    )
    assert intake_job_id(case) == "intake:P1:E1"

    redis = MagicMock()
    redis.enqueue_job = AsyncMock()
    await enqueue_intake_case(redis, case)
    redis.enqueue_job.assert_called_once()
    assert redis.enqueue_job.call_args[0][0] == "run_intake"
    assert redis.enqueue_job.call_args.kwargs["_job_id"] == "intake:P1:E1"
