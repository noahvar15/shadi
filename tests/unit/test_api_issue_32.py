"""Tests for API track issue #32: POST /cases intake and arq enqueue."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from tests.conftest import reload_api_modules


@contextmanager
def _patched_app(monkeypatch: pytest.MonkeyPatch, mock_conn: AsyncMock):
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
            yield client, mock_arq


def test_post_cases_stub_returns_queued_and_enqueues(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    with _patched_app(monkeypatch, mock_conn) as (client, mock_arq):
        r = client.post("/cases", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    UUID(body["case_id"])
    mock_conn.execute.assert_awaited_once()
    mock_arq.enqueue_job.assert_awaited_once()
    call = mock_arq.enqueue_job.await_args
    assert call.args[0] == "tasks.pipeline.run_diagnostic_pipeline"
    assert call.kwargs.get("_queue_name") == "arq:intake"


def test_post_cases_invalid_bundle_422_without_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")

    from api.config import get_settings

    get_settings.cache_clear()

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    mock_pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    mock_pool.acquire = _acquire
    mock_pool.close = AsyncMock()
    mock_arq = MagicMock()
    mock_arq.enqueue_job = AsyncMock()
    mock_arq.close = AsyncMock()

    settings_no_stub = MagicMock()
    settings_no_stub.stub_case_intake = False
    settings_no_stub.intake_queue = "arq:intake"

    with (
        patch("api.db.init_pool", AsyncMock(return_value=mock_pool)),
        patch("arq.create_pool", AsyncMock(return_value=mock_arq)),
        patch("api.db.close_pool", AsyncMock()),
    ):
        reload_api_modules()
        import api.config as api_config
        import api.main as api_main

        gs = api_config.get_settings
        api_main.app.dependency_overrides[gs] = lambda: settings_no_stub
        try:
            with TestClient(api_main.app) as client:
                r = client.post(
                    "/cases",
                    json={"resourceType": "Bundle", "type": "collection", "entry": []},
                )
        finally:
            api_main.app.dependency_overrides.pop(gs, None)

    assert r.status_code == 422
    mock_conn.execute.assert_not_awaited()
    mock_arq.enqueue_job.assert_not_awaited()
    get_settings.cache_clear()


def test_post_cases_accepts_valid_sample_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real FHIR path: CaseObject.from_fhir_bundle (no stub env)."""
    bundle_path = Path(__file__).resolve().parents[1] / "fixtures" / "sample_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")
    monkeypatch.setenv("SHADI_STUB_CASE_INTAKE", "0")

    from api.config import get_settings

    get_settings.cache_clear()

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
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
            r = client.post("/cases", json=bundle)

    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    mock_conn.execute.assert_awaited()
    mock_arq.enqueue_job.assert_awaited_once()
    get_settings.cache_clear()
