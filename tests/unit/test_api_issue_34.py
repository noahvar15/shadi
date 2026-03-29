"""Tests for API track issue #34: arq worker wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tasks.pipeline import run_diagnostic_pipeline
from tasks.worker import WorkerSettings, shutdown, startup


def test_worker_settings_exposes_pipeline_and_hooks() -> None:
    assert run_diagnostic_pipeline in WorkerSettings.functions
    assert WorkerSettings.on_startup is startup
    assert WorkerSettings.on_shutdown is shutdown
    assert WorkerSettings.queue_name
    assert WorkerSettings.redis_settings is not None


def test_worker_settings_dict_protocol_matches_lazy_snapshot() -> None:
    """Regression: dict views must not be empty (arq / dict() / iteration)."""
    from arq.worker import get_kwargs

    m = dict(WorkerSettings)
    assert bool(WorkerSettings)
    assert len(WorkerSettings) == len(m)
    assert set(m.keys()) == set(WorkerSettings.keys())
    assert get_kwargs(WorkerSettings) == m
    assert run_diagnostic_pipeline in m["functions"]


@pytest.mark.asyncio
async def test_worker_startup_stores_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@127.0.0.1:9/nope")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:9/0")

    from api.config import get_settings

    get_settings.cache_clear()

    mock_pool = MagicMock()
    with patch("tasks.worker.init_pool", AsyncMock(return_value=mock_pool)):
        ctx: dict = {}
        await startup(ctx)
    assert ctx["pool"] is mock_pool
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_worker_shutdown_closes_pool_via_close_pool() -> None:
    mock_pool = MagicMock()
    ctx = {"pool": mock_pool}
    with patch("tasks.worker.close_pool", AsyncMock()) as m_close:
        await shutdown(ctx)
    m_close.assert_awaited_once_with(mock_pool)


def test_worker_queue_name_follows_intake_queue_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    from api.config import get_settings

    monkeypatch.setenv("INTAKE_QUEUE", "arq:custom-test-queue")
    get_settings.cache_clear()
    import tasks.worker as tw

    importlib.reload(tw)
    assert tw.WorkerSettings.queue_name == "arq:custom-test-queue"
    monkeypatch.delenv("INTAKE_QUEUE", raising=False)
    get_settings.cache_clear()
    importlib.reload(tw)
