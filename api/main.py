"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import build_fhir_mcp_server, get_settings
from api.db import close_pool, init_pool
from api.routes import cases, fhir_routes, patients, reports

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("shadi.startup")
    app.state.settings = settings
    app.state.fhir_mcp = None
    pool = await init_pool(settings.database_url)
    app.state.pool = pool
    arq_redis = None
    try:
        try:
            arq_redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            app.state.arq_redis = arq_redis
        except Exception:
            try:
                await close_pool(pool)
            except Exception as exc:  # noqa: BLE001
                logger.warning("shadi.startup.cleanup.db_failed", err=str(exc))
            pool = None
            raise
        try:
            if settings.fhir_mcp_enabled:
                mcp = build_fhir_mcp_server(settings)
                await mcp.start()
                app.state.fhir_mcp = mcp
            yield
        finally:
            logger.info("shadi.shutdown")
            if app.state.fhir_mcp is not None:
                try:
                    await app.state.fhir_mcp.stop()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("shadi.shutdown.fhir_mcp_stop_failed", err=str(exc))
            if arq_redis is not None:
                try:
                    await arq_redis.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("shadi.shutdown.arq_close_failed", err=str(exc))
    finally:
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

_settings = get_settings()
_origins = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(fhir_routes.router, prefix="/fhir", tags=["fhir"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict:
    """Deep readiness probe — verifies Postgres and Redis connectivity."""
    checks: dict[str, str] = {}
    pool = getattr(app.state, "pool", None)
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = f"error: {exc}"
    else:
        checks["postgres"] = "no pool"

    arq_redis = getattr(app.state, "arq_redis", None)
    if arq_redis is not None:
        try:
            await arq_redis.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
    else:
        checks["redis"] = "no connection"

    all_ok = all(v == "ok" for v in checks.values())
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )
