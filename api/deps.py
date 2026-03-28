"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

import asyncpg
from arq.connections import ArqRedis
from fastapi import Depends, Request

from api.config import Settings, get_settings


def get_db_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_redis


SettingsDep = Annotated[Settings, Depends(get_settings)]
PoolDep = Annotated[asyncpg.Pool, Depends(get_db_pool)]
ArqDep = Annotated[ArqRedis, Depends(get_arq_pool)]
