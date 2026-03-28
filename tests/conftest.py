"""Shared pytest helpers."""

from __future__ import annotations

import importlib
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


def reload_api_modules() -> None:
    """Reload API package so tests get fresh FastAPI routes and Settings cache."""
    import api.config as api_config
    import api.deps as api_deps
    import api.main as api_main
    import api.routes.cases as api_cases
    import api.routes.reports as api_reports

    importlib.reload(api_config)
    importlib.reload(api_deps)
    importlib.reload(api_cases)
    importlib.reload(api_reports)
    importlib.reload(api_main)


@contextmanager
def patched_api_app(monkeypatch: pytest.MonkeyPatch, mock_conn: AsyncMock):
    """Fake DB pool + arq Redis; yields ``(client, mock_arq, mock_conn)``."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")
    monkeypatch.setenv("API_SECRET_KEY", "test-secret-key-for-pytest")
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
            yield client, mock_arq, mock_conn
