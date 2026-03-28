"""arq worker settings: DB pool in job context for ``run_diagnostic_pipeline``."""

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from api.config import get_settings
from api.db import close_pool, init_pool
from tasks.pipeline import run_diagnostic_pipeline

_settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    """Open the asyncpg pool and store it on the arq job context."""
    ctx["pool"] = await init_pool(_settings.database_url)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Close the pool created in ``startup``."""
    await close_pool(ctx.get("pool"))


class WorkerSettings:
    """arq ``Worker`` constructor kwargs for ``arq tasks.worker.WorkerSettings``."""
    functions = [run_diagnostic_pipeline]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = _settings.intake_queue
    on_startup = startup
    on_shutdown = shutdown
