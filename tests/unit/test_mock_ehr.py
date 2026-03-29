"""Mock EHR OAuth + Subscription (issue #70)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tools.mock_ehr.app import app


@pytest.fixture(autouse=True)
def _clear_mock_subscriptions() -> None:
    app.state.subscriptions.clear()


@pytest.mark.asyncio
async def test_oauth_token_client_credentials() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "mock-ehr-client",
                "client_secret": "mock-ehr-secret",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["expires_in"] == 3600


@pytest.mark.asyncio
async def test_oauth_rejects_bad_secret() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "mock-ehr-client",
                "client_secret": "wrong",
            },
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_subscription_crud() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sub = {
            "resourceType": "Subscription",
            "status": "active",
            "criteria": "Encounter?status=arrived",
            "channel": {
                "type": "rest-hook",
                "endpoint": "http://127.0.0.1:8000/fhir/notify",
            },
        }
        r = await client.post("/Subscription", json=sub)
        assert r.status_code == 200
        created = r.json()
        sid = created["id"]
        assert sid

        r2 = await client.delete(f"/Subscription/{sid}")
        assert r2.status_code == 204

        r3 = await client.delete(f"/Subscription/{sid}")
        assert r3.status_code == 404
