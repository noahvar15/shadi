"""arq worker settings: DB pool in job context for ``run_diagnostic_pipeline``."""

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from api.config import get_settings
from api.db import close_pool, init_pool
from tasks.pipeline import run_diagnostic_pipeline


def _arq_worker_kwargs_filtered() -> dict[str, Any]:
    """Kwargs arq's ``Worker`` accepts, built lazily (``get_settings()`` not at import)."""
    from inspect import signature

    from arq.worker import Worker

    s = get_settings()
    snap = {
        "functions": [run_diagnostic_pipeline],
        "redis_settings": RedisSettings.from_dsn(s.redis_url),
        "queue_name": s.intake_queue,
        "on_startup": startup,
        "on_shutdown": shutdown,
    }
    worker_args = set(signature(Worker).parameters.keys())
    return {k: v for k, v in snap.items() if k in worker_args}


async def startup(ctx: dict[str, Any]) -> None:
    """Open the asyncpg pool and store it on the arq job context."""
    settings = get_settings()
    ctx["pool"] = await init_pool(settings.database_url)


async def shutdown(ctx: dict[str, Any]) -> None:
    """Close the pool created in ``startup``."""
    await close_pool(ctx.get("pool"))


class _ArqWorkerSettings(dict):
    """Dict-shaped arq settings: reads delegate to a lazy snapshot (no import-time env).

    Subclasses ``dict`` so ``isinstance(..., dict)`` and arq's ``get_kwargs`` path work.
    All read operations go through the same filtered mapping so ``dict(WorkerSettings)``,
    iteration, ``keys()``, and ``bool()`` stay consistent (not an empty backing dict).
    """

    __slots__ = ()

    def _mapping(self) -> dict[str, Any]:
        return _arq_worker_kwargs_filtered()

    def __getitem__(self, key: str) -> Any:  # type: ignore[override]
        return self._mapping()[key]

    def __iter__(self):  # type: ignore[override]
        return iter(self._mapping())

    def __len__(self) -> int:  # type: ignore[override]
        return len(self._mapping())

    def __bool__(self) -> bool:
        return bool(self._mapping())

    def __contains__(self, key: object) -> bool:  # type: ignore[override]
        return key in self._mapping()

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        return self._mapping().get(key, default)

    def keys(self):  # type: ignore[override]
        return self._mapping().keys()

    def values(self):  # type: ignore[override]
        return self._mapping().values()

    def items(self):  # type: ignore[override]
        return self._mapping().items()

    def copy(self) -> dict[str, Any]:  # type: ignore[override]
        return self._mapping().copy()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        m = self._mapping()
        if name in m:
            return m[name]
        raise AttributeError(name)

    def __setitem__(self, key: Any, value: Any) -> None:  # type: ignore[override]
        raise TypeError("WorkerSettings mapping is read-only")

    def __delitem__(self, key: Any) -> None:  # type: ignore[override]
        raise TypeError("WorkerSettings mapping is read-only")


WorkerSettings: _ArqWorkerSettings = _ArqWorkerSettings()
