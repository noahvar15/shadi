"""arq worker settings: DB pool in job context for ``run_diagnostic_pipeline``."""

from __future__ import annotations

import os
from typing import Any

from arq.connections import RedisSettings

from api.config import get_settings
from api.db import close_pool, init_pool
from tasks.pipeline import run_diagnostic_pipeline


async def startup(ctx: dict[str, Any]) -> None:
    """Open the asyncpg pool and store it on the arq job context."""
    settings = get_settings()
    ctx["pool"] = await init_pool(settings.database_url)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Close the pool created in ``startup``."""
    await close_pool(ctx.get("pool"))


class WorkerSettings:
    """arq ``Worker`` constructor kwargs for ``arq tasks.worker.WorkerSettings``."""

    functions = [run_diagnostic_pipeline]
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    )
    queue_name = os.environ.get("INTAKE_QUEUE", "arq:intake")
    on_startup = startup
    on_shutdown = shutdown
