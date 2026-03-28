"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import Settings, build_fhir_mcp_server
from api.routes import cases, fhir_routes, reports

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("shadi.startup")
    settings = Settings()
    app.state.settings = settings
    app.state.fhir_mcp = None
    if settings.fhir_mcp_enabled:
        mcp = build_fhir_mcp_server(settings)
        await mcp.start()
        app.state.fhir_mcp = mcp
    # TODO: initialise DB pool, Redis connection, vLLM client (#31)
    yield
    if app.state.fhir_mcp is not None:
        await app.state.fhir_mcp.stop()
    logger.info("shadi.shutdown")


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
app.include_router(fhir_routes.router, prefix="/fhir", tags=["fhir"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
