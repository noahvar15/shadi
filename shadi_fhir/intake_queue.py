"""Enqueue normalized cases for the intake / diagnostic pipeline (arq).

The job name ``run_intake`` must match the worker registration in ``tasks.pipeline``
when the backend platform track wires the arq worker (see cross-track-dependencies).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from agents.schemas import CaseObject

if TYPE_CHECKING:
    from arq.connections import ArqRedis


def intake_job_id(case: CaseObject) -> str:
    """Stable arq job id so Subscription rest-hook retries do not enqueue duplicate runs."""
    return f"intake:{case.patient_id}:{case.encounter_id}"


async def create_intake_pool(redis_url: str, queue_name: str) -> ArqRedis:
    from arq import create_pool
    from arq.connections import RedisSettings

    settings = RedisSettings.from_dsn(redis_url)
    settings = replace(settings, queue_name=queue_name)
    return await create_pool(settings)


async def enqueue_intake_case(redis: ArqRedis, case: CaseObject) -> None:
    """Push ``case`` JSON onto the intake queue for ``run_intake``."""
    await redis.enqueue_job(
        "run_intake",
        case.model_dump(mode="json"),
        _job_id=intake_job_id(case),
    )
