"""arq worker settings: DB pool in job context for ``run_diagnostic_pipeline``."""

from __future__ import annotations

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


class _ArqWorkerSettings(dict):
    """Lazy arq kwargs (dict form) so importing this module does not call ``get_settings()``."""

    __slots__ = ()

    def _snapshot(self) -> dict[str, Any]:
        s = get_settings()
        return {
            "functions": [run_diagnostic_pipeline],
            "redis_settings": RedisSettings.from_dsn(s.redis_url),
            "queue_name": s.intake_queue,
            "on_startup": startup,
            "on_shutdown": shutdown,
        }

    def items(self):  # type: ignore[override]
        from inspect import signature

        from arq.worker import Worker

        snap = self._snapshot()
        worker_args = set(signature(Worker).parameters.keys())
        return [(k, v) for k, v in snap.items() if k in worker_args]

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        snap = self._snapshot()
        try:
            return snap[name]
        except KeyError as e:
            raise AttributeError(name) from e


WorkerSettings: _ArqWorkerSettings = _ArqWorkerSettings()
