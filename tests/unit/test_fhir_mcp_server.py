"""Tests for FHIR MCP server: OAuth (#26), Subscription + notify (#27), stop (#29)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from shadi_fhir.exceptions import FHIRAuthError
from shadi_fhir.mcp_server import FHIRMCPServer

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "sample_bundle.json"


def _load_bundle() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


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
        notification_endpoint="https://shadi.local/fhir/notify",
        redis_url="redis://localhost:6379/0",
        intake_queue="shadi:test",
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


@pytest.mark.asyncio
async def test_start_registers_subscription() -> None:
    server = _make_server()
    token_url = server._token_url
    base = server._base_url

    async def post_side_effect(url: str, **kwargs: object) -> httpx.Response:
        u = str(url)
        if u == token_url:
            return _http_response(
                200,
                json_data={"access_token": "t", "expires_in": 3600},
                url=u,
            )
        if u.endswith("/Subscription") or u == "/Subscription":
            return _http_response(
                201,
                json_data={"resourceType": "Subscription", "id": "sub-99"},
                url=f"{base}/Subscription",
            )
        raise AssertionError(f"unexpected POST {u!r}")

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(side_effect=post_side_effect)
    mock_http.delete = AsyncMock()
    mock_http.aclose = AsyncMock()

    mock_arq = AsyncMock()
    mock_arq.enqueue_job = AsyncMock()
    mock_arq.close = AsyncMock()

    with patch("shadi_fhir.mcp_server.httpx.AsyncClient", return_value=mock_http):
        with patch(
            "shadi_fhir.mcp_server.create_intake_pool",
            AsyncMock(return_value=mock_arq),
        ):
            await server.start()

    assert server._subscription_id == "sub-99"
    await server.stop()
    mock_arq.close.assert_awaited()
    mock_http.aclose.assert_awaited()


@pytest.mark.asyncio
async def test_handle_notification_enqueues_when_arq_ready() -> None:
    server = _make_server()
    mock_arq = AsyncMock()
    mock_arq.enqueue_job = AsyncMock()
    server._arq = mock_arq
    server._http = AsyncMock()

    case = await server.handle_notification(_load_bundle())
    assert case.patient_id == "pat-sample-1"
    mock_arq.enqueue_job.assert_awaited_once()
    args, _kwargs = mock_arq.enqueue_job.call_args
    assert args[0] == "run_intake"
    assert args[1]["patient_id"] == "pat-sample-1"
