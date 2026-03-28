"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.db import close_pool, init_pool
from api.routes import cases, reports

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("shadi.startup")
    pool = None
    arq_redis = None
    try:
        pool = await init_pool(settings.database_url)
        arq_redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        app.state.pool = pool
        app.state.arq_redis = arq_redis
    except Exception:
        if arq_redis is not None:
            try:
                await arq_redis.close()
            except Exception as exc:  # noqa: BLE001 — defensive cleanup
                logger.warning("shadi.startup.cleanup.arq_failed", err=str(exc))
        if pool is not None:
            try:
                await close_pool(pool)
            except Exception as exc:  # noqa: BLE001
                logger.warning("shadi.startup.cleanup.db_failed", err=str(exc))
        raise

    try:
        yield
    finally:
        logger.info("shadi.shutdown")
        if arq_redis is not None:
            try:
                await arq_redis.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("shadi.shutdown.arq_close_failed", err=str(exc))
        if pool is not None:
            try:
                await close_pool(pool)
            except Exception as exc:  # noqa: BLE001
                logger.warning("shadi.shutdown.db_close_failed", err=str(exc))


app = FastAPI(
    title="Shadi",
    description="Multi-agent clinical diagnostic reasoning API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
