"""arq worker settings — run: ``arq tasks.worker.WorkerSettings``."""

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from api.config import get_settings
from api.db import close_pool, init_pool
from tasks.pipeline import run_diagnostic_pipeline


def _worker_redis_and_queue() -> tuple[RedisSettings, str]:
    s = get_settings()
    return RedisSettings.from_dsn(s.redis_url), s.intake_queue


_redis_settings, _queue_name = _worker_redis_and_queue()


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    ctx["pool"] = await init_pool(settings.database_url)


async def shutdown(ctx: dict[str, Any]) -> None:
    pool = ctx.get("pool")
    if pool is not None:
        await close_pool(pool)


class WorkerSettings:
    functions = [run_diagnostic_pipeline]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings
    queue_name = _queue_name
