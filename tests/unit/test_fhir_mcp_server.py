"""Tests for FHIR MCP server OAuth (issue #26)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from shadi_fhir.exceptions import FHIRAuthError
from shadi_fhir.mcp_server import FHIRMCPServer


def _http_response(
    status: int,
    *,
    json_data: dict | None = None,
    method: str = "POST",
    url: str = "https://example.org/x",
) -> httpx.Response:
    kw: dict = {"request": httpx.Request(method, url)}
    if json_data is not None:
        kw["json"] = json_data
    return httpx.Response(status, **kw)


def _make_server() -> FHIRMCPServer:
    return FHIRMCPServer(
        "https://fhir.example.org/R4",
        "client-id",
        "secret",
        "https://auth.example.org/oauth2/token",
    )


@pytest.mark.asyncio
async def test_oauth_failure_raises_fhir_auth_error() -> None:
    server = _make_server()
    bad = _http_response(401, json_data={"error": "invalid_client"}, url=server._token_url)
    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=bad)
    mock_http.aclose = AsyncMock()
    server._http = mock_http
    with pytest.raises(FHIRAuthError):
        await server._refresh_token()


@pytest.mark.asyncio
async def test_get_token_cached_within_ttl() -> None:
    server = _make_server()
    ok = _http_response(
        200,
        json_data={"access_token": "tok1", "expires_in": 3600},
        url=server._token_url,
    )
    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=ok)
    server._http = mock_http
    await server._refresh_token()
    t1 = await server._get_token()
    t2 = await server._get_token()
    assert t1 == t2 == "tok1"
    assert mock_http.post.await_count == 1
