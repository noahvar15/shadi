"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import cases, reports

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("shadi.startup")
    # TODO: initialise DB pool, Redis connection, vLLM client
    yield
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
