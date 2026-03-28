"""FHIR R4 MCP server — OAuth (#26), Subscription + notify (#27), clean shutdown (#29)."""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from agents.schemas import CaseObject
from shadi_fhir.exceptions import FHIRAuthError
from shadi_fhir.intake_queue import create_intake_pool, enqueue_intake_case
from shadi_fhir.normalizer import FHIRNormalizer

logger = structlog.get_logger()

_OAUTH_SCOPE = "system/Encounter.read system/Patient.read"


class FHIRMCPServer:
    """Subscribes to FHIR R4 encounter events from Epic/Cerner."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        *,
        notification_endpoint: str,
        redis_url: str,
        intake_queue: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._notification_endpoint = notification_endpoint
        self._redis_url = redis_url
        self._intake_queue = intake_queue
        self._normalizer = FHIRNormalizer()
        self._http: httpx.AsyncClient | None = None
        self._arq: Any = None
        self._subscription_id: str | None = None
        self._access_token: str | None = None
        self._token_deadline_monotonic: float = 0.0

    async def _refresh_token(self) -> None:
        if self._http is None:
            raise RuntimeError("HTTP client not initialised")
        resp = await self._http.post(
            self._token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": _OAUTH_SCOPE,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code in (400, 401):
            logger.warning(
                "fhir.oauth.token_failed",
                status_code=resp.status_code,
                body_preview=resp.text[:200],
            )
            raise FHIRAuthError(f"OAuth token request failed: HTTP {resp.status_code}")
        resp.raise_for_status()
        body = resp.json()
        token = body.get("access_token")
        if not token or not isinstance(token, str):
            raise FHIRAuthError("OAuth token response missing access_token")
        raw_expires = body.get("expires_in", 300)
        try:
            expires_in = float(raw_expires)
        except (TypeError, ValueError):
            logger.warning("fhir.oauth.invalid_expires_in", value=raw_expires)
            expires_in = 300.0
        if expires_in <= 0:
            logger.warning("fhir.oauth.nonpositive_expires_in", value=raw_expires)
            expires_in = 300.0
        expires_in = max(60.0, expires_in)
        self._access_token = token
        self._token_deadline_monotonic = time.monotonic() + expires_in
        logger.info("fhir.oauth.token_ok", expires_in=expires_in)

    async def _get_token(self) -> str:
        if (
            self._access_token
            and time.monotonic() < self._token_deadline_monotonic - 60
        ):
            return self._access_token
        await self._refresh_token()
        assert self._access_token is not None
        return self._access_token

    def _fhir_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
        }

    async def _register_subscription(self) -> None:
        if self._http is None:
            raise RuntimeError("HTTP client not initialised")
        token = await self._get_token()
        payload = {
            "resourceType": "Subscription",
            "status": "active",
            "reason": "Notify Shadi when an Encounter reaches arrived status for intake processing",
            "criteria": "Encounter?status=arrived",
            "channel": {
                "type": "rest-hook",
                "endpoint": self._notification_endpoint,
                "payload": "application/fhir+json",
            },
        }
        resp = await self._http.post(
            "/Subscription",
            json=payload,
            headers=self._fhir_headers(token),
        )
        resp.raise_for_status()
        body = resp.json()
        sid = body.get("id")
        if not sid:
            raise RuntimeError("FHIR Subscription response missing id")
        self._subscription_id = str(sid)
        logger.info("fhir.subscription.registered", subscription_id=self._subscription_id)

    async def start(self) -> None:
        """Authenticate, connect Redis/arq, and register encounter subscription."""
        self._http = httpx.AsyncClient(base_url=self._base_url, timeout=60.0)
        arq_pool: Any = None
        try:
            await self._refresh_token()
            arq_pool = await create_intake_pool(self._redis_url, self._intake_queue)
            self._arq = arq_pool
            await self._register_subscription()
        except Exception:
            self._arq = None
            if arq_pool is not None:
                await arq_pool.close()
            if self._http is not None:
                await self._http.aclose()
                self._http = None
            self._access_token = None
            self._subscription_id = None
            raise
        logger.info("fhir.mcp_server.started", base_url=self._base_url)

    async def stop(self) -> None:
        """DELETE Subscription (best-effort), close arq pool and HTTP client."""
        if self._subscription_id and self._http is not None:
            try:
                token = await self._get_token()
                r = await self._http.delete(
                    f"/Subscription/{self._subscription_id}",
                    headers=self._fhir_headers(token),
                )
                if r.status_code == 404:
                    logger.info(
                        "fhir.subscription.already_deleted",
                        subscription_id=self._subscription_id,
                    )
                elif not r.is_success:
                    logger.warning(
                        "fhir.subscription.delete_status",
                        status_code=r.status_code,
                        subscription_id=self._subscription_id,
                    )
            except Exception as exc:
                logger.warning(
                    "fhir.subscription.delete_exception",
                    exc_type=type(exc).__name__,
                    error=str(exc),
                )
        self._subscription_id = None
        if self._arq is not None:
            try:
                await self._arq.close()
            finally:
                self._arq = None
        if self._http is not None:
            try:
                await self._http.aclose()
            finally:
                self._http = None
        self._access_token = None
        self._token_deadline_monotonic = 0.0
        logger.info("fhir.mcp_server.stopped")

    async def handle_notification(self, bundle: dict[str, Any]) -> CaseObject:
        """Normalize a notification bundle and enqueue it for intake processing."""
        case = self._normalizer.bundle_to_case(bundle)
        if self._arq is not None:
            await enqueue_intake_case(self._arq, case)
        else:
            logger.warning("fhir.notify.enqueue_skipped", reason="arq_pool_not_initialized")
        return case
