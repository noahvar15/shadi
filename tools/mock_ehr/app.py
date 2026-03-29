"""In-memory mock EHR: OAuth token, Subscription CRUD, demo rest-hook to Shadi."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shadi_fhir.triage_bundle import build_triage_bundle

logger = structlog.get_logger()


class MockEHRSettings(BaseSettings):
    """Env for ``python -m tools.mock_ehr`` — keep in sync with ``.env.example``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mock_ehr_client_id: str = Field(default="mock-ehr-client", validation_alias="MOCK_EHR_CLIENT_ID")
    mock_ehr_client_secret: str = Field(
        default="mock-ehr-secret",
        validation_alias="MOCK_EHR_CLIENT_SECRET",
    )
    shadi_notify_url: str = Field(
        default="http://127.0.0.1:8000/fhir/notify",
        validation_alias="MOCK_EHR_SHADI_NOTIFY_URL",
    )
    shadi_webhook_secret: str = Field(default="", validation_alias="MOCK_EHR_SHADI_WEBHOOK_SECRET")


_settings: MockEHRSettings | None = None


def get_mock_settings() -> MockEHRSettings:
    global _settings
    if _settings is None:
        _settings = MockEHRSettings()
    return _settings


def create_app() -> FastAPI:
    app = FastAPI(title="Shadi Mock EHR", version="0.1.0")
    app.state.subscriptions: dict[str, dict[str, Any]] = {}

    @app.post("/oauth/token")
    async def oauth_token(request: Request) -> dict[str, Any]:
        """SMART-style client_credentials (form body)."""
        body = await request.body()
        from urllib.parse import parse_qs

        data = parse_qs(body.decode("utf-8"))
        grant = (data.get("grant_type") or [""])[0]
        cid = (data.get("client_id") or [""])[0]
        secret = (data.get("client_secret") or [""])[0]
        if grant != "client_credentials":
            raise HTTPException(status_code=400, detail="unsupported_grant_type")
        s = get_mock_settings()
        if cid != s.mock_ehr_client_id or secret != s.mock_ehr_client_secret:
            raise HTTPException(status_code=401, detail="invalid_client")
        return {
            "access_token": "mock-ehr-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    @app.post("/Subscription", response_model=None)
    async def create_subscription(resource: dict[str, Any]) -> dict[str, Any]:
        if resource.get("resourceType") != "Subscription":
            raise HTTPException(status_code=400, detail="Expected Subscription")
        sid = str(uuid.uuid4())
        out = dict(resource)
        out["id"] = sid
        app.state.subscriptions[sid] = out
        logger.info("mock_ehr.subscription.created", id=sid)
        return out

    @app.delete("/Subscription/{subscription_id}", status_code=204)
    async def delete_subscription(subscription_id: str) -> None:
        if subscription_id not in app.state.subscriptions:
            raise HTTPException(status_code=404, detail="Not found")
        del app.state.subscriptions[subscription_id]
        logger.info("mock_ehr.subscription.deleted", id=subscription_id)

    @app.get("/Subscription")
    async def list_subscriptions() -> dict[str, Any]:
        """Optional introspection for demos."""
        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "entry": [{"resource": v} for v in app.state.subscriptions.values()],
        }

    class SimulateBody(BaseModel):
        patient_id: str = "demo-patient-1"
        encounter_id: str | None = None
        triage_text: str = Field(..., min_length=1)
        chief_complaint: str | None = None

    @app.post("/$demo/simulate-arrived-encounter")
    async def simulate_arrived_encounter(body: SimulateBody) -> dict[str, Any]:
        """Build a triage bundle and POST it to Shadi ``/fhir/notify`` (rest-hook simulation)."""
        eid = body.encounter_id or f"enc-{uuid.uuid4().hex[:12]}"
        bundle = build_triage_bundle(
            patient_id=body.patient_id,
            encounter_id=eid,
            triage_text=body.triage_text,
            chief_complaint=body.chief_complaint,
        )
        raw = json.dumps(bundle, separators=(",", ":")).encode("utf-8")
        s = get_mock_settings()
        headers: dict[str, str] = {
            "Content-Type": "application/fhir+json",
            "Accept": "application/json",
        }
        if s.shadi_webhook_secret.strip():
            digest = hmac.new(s.shadi_webhook_secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
            headers["X-Shadi-Signature"] = f"sha256={digest}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                r = await client.post(s.shadi_notify_url, content=raw, headers=headers)
            except httpx.RequestError as exc:
                logger.exception("mock_ehr.notify_failed")
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not reach Shadi: {exc}",
                ) from exc

        detail: dict[str, Any] = {
            "shadi_status_code": r.status_code,
            "encounter_id": eid,
            "patient_id": body.patient_id,
        }
        try:
            detail["shadi_body"] = r.json()
        except Exception:
            detail["shadi_text"] = r.text[:500]

        if not r.is_success:
            raise HTTPException(status_code=502, detail=detail)
        return {"status": "ok", **detail}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "mock-ehr"}

    return app


app = create_app()
