"""arq worker settings: DB pool in job context for ``run_diagnostic_pipeline``."""

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from api.config import get_settings
from api.db import close_pool, init_pool
from tasks.pipeline import run_diagnostic_pipeline


class _WorkerQueueSettings(BaseSettings):
    """Redis URL + queue name only — matches ``api.config.Settings`` env loading (``.env``)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    intake_queue: str = Field(default="arq:intake", validation_alias="INTAKE_QUEUE")


_worker_queue = _WorkerQueueSettings()


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
    redis_settings = RedisSettings.from_dsn(_worker_queue.redis_url)
    queue_name = _worker_queue.intake_queue
    on_startup = startup
    on_shutdown = shutdown
