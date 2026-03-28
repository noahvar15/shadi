"""FHIR R4 MCP server — SMART on FHIR authentication (issue #26).

Subscription registration, notifications, and subscription teardown are
implemented in issues #27 and #29.
"""

from __future__ import annotations

import time

import httpx
import structlog

from shadi_fhir.exceptions import FHIRAuthError

logger = structlog.get_logger()

_OAUTH_SCOPE = "system/Encounter.read system/Patient.read"


class FHIRMCPServer:
    """OAuth2 client-credentials client for FHIR R4 APIs (Epic/Cerner)."""

    def __init__(self, base_url: str, client_id: str, client_secret: str, token_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._http: httpx.AsyncClient | None = None
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
        expires_in = float(body.get("expires_in", 300))
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

    async def start(self) -> None:
        """Create HTTP client and obtain an access token."""
        self._http = httpx.AsyncClient(base_url=self._base_url, timeout=60.0)
        try:
            await self._refresh_token()
        except Exception:
            if self._http is not None:
                await self._http.aclose()
                self._http = None
            self._access_token = None
            raise
        logger.info("fhir.mcp_server.started", base_url=self._base_url)

    async def stop(self) -> None:
        """Close the FHIR HTTP client."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        self._access_token = None
        self._token_deadline_monotonic = 0.0
        logger.info("fhir.mcp_server.stopped")
