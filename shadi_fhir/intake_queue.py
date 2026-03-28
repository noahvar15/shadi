"""Enqueue normalized cases for the intake / diagnostic pipeline (arq).

The job name ``run_intake`` must match the worker registration in ``tasks.pipeline``
when the backend platform track wires the arq worker (see cross-track-dependencies).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from agents.schemas import CaseObject

if TYPE_CHECKING:
    pass


async def create_intake_pool(redis_url: str, queue_name: str) -> ArqRedis:
    settings = RedisSettings.from_dsn(redis_url)
    settings = replace(settings, queue_name=queue_name)
    return await create_pool(settings)


async def enqueue_intake_case(redis: ArqRedis, case: CaseObject) -> None:
    """Push ``case`` JSON onto the intake queue for ``run_intake``."""
    await redis.enqueue_job(
        "run_intake",
        case.model_dump(mode="json"),
    )
