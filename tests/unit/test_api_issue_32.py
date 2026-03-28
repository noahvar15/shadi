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
def _cases_api_with_mocks(
    monkeypatch: pytest.MonkeyPatch,
    mock_conn: AsyncMock,
    *,
    shadi_stub_env: str | None = "1",
    settings_override: MagicMock | None = None,
):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")
    if shadi_stub_env is not None:
        monkeypatch.setenv("SHADI_STUB_CASE_INTAKE", shadi_stub_env)
    else:
        monkeypatch.delenv("SHADI_STUB_CASE_INTAKE", raising=False)

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
        import api.config as api_config
        import api.main as api_main

        if settings_override is not None:
            api_main.app.dependency_overrides[api_config.get_settings] = lambda: settings_override
        try:
            with TestClient(api_main.app) as client:
                yield client, mock_arq
        finally:
            if settings_override is not None:
                api_main.app.dependency_overrides.pop(api_config.get_settings, None)


def test_post_cases_stub_returns_queued_and_enqueues(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    with _cases_api_with_mocks(monkeypatch, mock_conn) as (client, mock_arq):
        r = client.post("/cases", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    UUID(body["case_id"])
    assert mock_conn.execute.await_count == 2
    mock_arq.enqueue_job.assert_awaited_once()
    call = mock_arq.enqueue_job.await_args
    assert call.args[0] == "tasks.pipeline.run_diagnostic_pipeline"
    assert call.kwargs.get("_queue_name") == "arq:intake"


def test_post_cases_invalid_bundle_422_without_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    settings_no_stub = MagicMock()
    settings_no_stub.stub_case_intake = False
    settings_no_stub.intake_queue = "arq:intake"

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    with _cases_api_with_mocks(
        monkeypatch,
        mock_conn,
        shadi_stub_env=None,
        settings_override=settings_no_stub,
    ) as (client, mock_arq):
        r = client.post(
            "/cases",
            json={"resourceType": "Bundle", "type": "collection", "entry": []},
        )

    assert r.status_code == 422
    mock_conn.execute.assert_not_awaited()
    mock_arq.enqueue_job.assert_not_awaited()

    from api.config import get_settings

    get_settings.cache_clear()


def test_post_cases_accepts_valid_sample_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real FHIR path: CaseObject.from_fhir_bundle (no stub env)."""
    bundle_path = Path(__file__).resolve().parents[1] / "fixtures" / "sample_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    with _cases_api_with_mocks(monkeypatch, mock_conn, shadi_stub_env="0") as (client, mock_arq):
        r = client.post("/cases", json=bundle)

    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    assert mock_conn.execute.await_count == 2
    mock_arq.enqueue_job.assert_awaited_once()

    from api.config import get_settings

    get_settings.cache_clear()
