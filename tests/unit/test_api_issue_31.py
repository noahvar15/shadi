"""Tests for API track issue #31: Settings, DB pool, Redis/arq lifespan."""

from __future__ import annotations

import importlib
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


@contextmanager
def _patched_lifespan(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")
    monkeypatch.setenv("API_SECRET_KEY", "test-secret-key-for-pytest")

    from api.config import get_settings

    get_settings.cache_clear()

    mock_pool = MagicMock()
    mock_pool.close = AsyncMock()

    @asynccontextmanager
    async def _acquire():
        yield AsyncMock()

    mock_pool.acquire = _acquire

    mock_arq = MagicMock()
    mock_arq.close = AsyncMock()

    with (
        patch("api.db.init_pool", AsyncMock(return_value=mock_pool)),
        patch("arq.create_pool", AsyncMock(return_value=mock_arq)),
        patch("api.db.close_pool", AsyncMock()),
    ):
        import api.config as api_config
        import api.deps as api_deps
        import api.main as api_main

        importlib.reload(api_config)
        importlib.reload(api_deps)
        importlib.reload(api_main)
        with TestClient(api_main.app) as client:
            yield client, mock_pool, mock_arq


def test_settings_reads_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://a:b@localhost:5432/x")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("API_SECRET_KEY", "test-secret-key-for-pytest")
    from api.config import Settings, get_settings

    get_settings.cache_clear()
    s = Settings()
    assert "postgresql" in s.database_url
    assert s.redis_url.startswith("redis://")
    get_settings.cache_clear()


def test_api_secret_rejects_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://a:b@localhost:5432/x")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("API_SECRET_KEY", "change-me")
    from api.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValueError, match="API_SECRET_KEY"):
        Settings()
    get_settings.cache_clear()


def test_lifespan_sets_pool_and_arq_on_state(monkeypatch: pytest.MonkeyPatch) -> None:
    with _patched_lifespan(monkeypatch) as (client, mock_pool, mock_arq):
        assert client.app.state.pool is mock_pool
        assert client.app.state.arq_redis is mock_arq
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ensure_schema_executes_ddl() -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock()
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire

    from api.db import ensure_schema

    await ensure_schema(pool)
    assert conn.execute.await_count >= 2
    executed = " ".join(str(c.args[0]) for c in conn.execute.await_args_list)
    assert "CREATE TABLE IF NOT EXISTS cases" in executed
    assert "cases_status_check" in executed
    assert "patient_id" in executed
    assert "cases_touch_updated_at" in executed

    from api.db import VALID_CASE_STATUSES

    assert "pending_enqueue" in VALID_CASE_STATUSES
    assert "complete" in VALID_CASE_STATUSES


@pytest.mark.asyncio
async def test_asyncpg_dsn_strips_plus_asyncpg(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_pool uses DSN without +asyncpg for asyncpg driver."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/db")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")
    monkeypatch.setenv("API_SECRET_KEY", "test-secret-key-for-pytest")

    from api.config import get_settings

    get_settings.cache_clear()

    created: list[str] = []

    async def fake_create_pool(dsn: str, **kwargs):
        created.append(dsn)
        raise RuntimeError("stop after pool creation attempt")

    with patch("asyncpg.create_pool", side_effect=fake_create_pool):
        from api.db import init_pool

        with pytest.raises(RuntimeError, match="stop after"):
            await init_pool(get_settings().database_url)

    assert created
    assert "+asyncpg" not in created[0]
    assert created[0].startswith("postgresql://")

    get_settings.cache_clear()
