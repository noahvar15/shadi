"""arq worker settings — run: ``arq tasks.worker.WorkerSettings``."""

from __future__ import annotations

import os
from typing import Any

from arq.connections import RedisSettings

from api.config import get_settings
from api.db import close_pool, init_pool
from tasks.pipeline import run_diagnostic_pipeline


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
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
    )
    queue_name = os.environ.get("INTAKE_QUEUE", "arq:intake")
