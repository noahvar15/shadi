"""API route tests with mocked Postgres + Redis/arq (no docker required)."""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from starlette.testclient import TestClient

from tests.conftest import reload_api_modules

# Minimal FHIR Bundle shape (stub intake still accepts a realistic document type).
_MINIMAL_FHIR_BUNDLE = {"resourceType": "Bundle", "type": "collection", "entry": []}


@contextmanager
def _app_test_client(monkeypatch: pytest.MonkeyPatch, mock_conn: AsyncMock):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")
    monkeypatch.setenv("SHADI_STUB_CASE_INTAKE", "1")

    from api.config import get_settings

    get_settings.cache_clear()

    mock_pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    mock_pool.acquire = _acquire
    mock_pool.close = AsyncMock()

    mock_arq = MagicMock()
    mock_arq.enqueue_job = AsyncMock()
    mock_arq.close = AsyncMock()

    with (
        patch("api.db.init_pool", AsyncMock(return_value=mock_pool)),
        patch("arq.create_pool", AsyncMock(return_value=mock_arq)),
        patch("api.db.close_pool", AsyncMock()),
    ):
        reload_api_modules()
        import api.main as api_main

        with TestClient(api_main.app) as client:
            yield client, mock_conn, mock_arq


@pytest.fixture
def mock_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, mock_conn: AsyncMock):
    from api.config import get_settings

    try:
        with _app_test_client(monkeypatch, mock_conn) as triplet:
            yield triplet
    finally:
        get_settings.cache_clear()


def test_health_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_conn = AsyncMock()
    with _app_test_client(monkeypatch, mock_conn) as (client, _, _):
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_post_cases_stub_queues_job(api_client) -> None:
    client, _mock_conn, mock_arq = api_client
    r = client.post("/cases", json=_MINIMAL_FHIR_BUNDLE)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    UUID(body["case_id"])
    mock_arq.enqueue_job.assert_awaited_once()


def test_post_cases_enqueue_failure_marks_row_and_503(api_client) -> None:
    client, mock_conn, mock_arq = api_client
    mock_arq.enqueue_job = AsyncMock(side_effect=RuntimeError("redis down"))
    r = client.post("/cases", json=_MINIMAL_FHIR_BUNDLE)
    assert r.status_code == 503
    assert mock_conn.execute.await_count >= 2
    fail_args = mock_conn.execute.await_args_list[-1].args
    assert fail_args[2] == "enqueue_failed"
    assert fail_args[3] == "enqueue_failed"


def test_report_status_not_found(api_client) -> None:
    client, mock_conn, _mock_arq = api_client
    mock_conn.fetchrow = AsyncMock(return_value=None)
    rid = str(uuid4())
    r = client.get(f"/reports/{rid}/status")
    assert r.status_code == 404


def test_report_status_queued(api_client) -> None:
    client, mock_conn, _mock_arq = api_client
    cid = uuid4()
    mock_conn.fetchrow = AsyncMock(
        return_value={"status": "queued", "error_message": None},
    )
    r = client.get(f"/reports/{cid}/status")
    assert r.status_code == 200
    assert r.json() == {"status": "queued", "error": None}


def test_get_report_not_ready(api_client) -> None:
    client, mock_conn, _mock_arq = api_client
    cid = uuid4()
    mock_conn.fetchrow = AsyncMock(
        return_value={"status": "queued", "report_json": None},
    )
    r = client.get(f"/reports/{cid}")
    assert r.status_code == 404


def test_get_report_ready(api_client) -> None:
    client, mock_conn, _mock_arq = api_client
    cid = uuid4()
    payload = {
        "case_id": str(cid),
        "synthesized_at": "2026-03-28T12:00:00",
        "top_diagnoses": [],
        "vetoed_recommendations": [],
        "consensus_level": 0.0,
        "divergent_agents": [],
        "fhir_diagnostic_report_id": None,
    }
    mock_conn.fetchrow = AsyncMock(
        return_value={"status": "complete", "report_json": payload},
    )
    r = client.get(f"/reports/{cid}")
    assert r.status_code == 200
    data = r.json()
    assert data["case_id"] == str(cid)
    assert data["consensus_level"] == 0.0
